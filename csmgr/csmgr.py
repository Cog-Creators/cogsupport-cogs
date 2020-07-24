import asyncio
import logging
import math
from typing import Any, Dict, List, Tuple

import aiohttp
import discord
import yarl
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.commands import NoParseOptional as Optional
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from .checks import is_core_dev_or_qa, is_senior_cog_creator
from .discord_ids import (
    COG_CREATOR_ROLE_ID,
    COG_SUPPORT_SERVER_ID,
    OTHERCOGS_ID,
    SENIOR_COG_CREATOR_ROLE_ID,
    V3_COG_SUPPORT_CATEGORY_ID,
)
from .repo import CONFIG_COG_NAME, CONFIG_IDENTIFIER, CreatorLevel, Repo
from .utils import grouper

log = logging.getLogger("red.cogsupport-cogs.csmgr")


class CSMgr(commands.Cog):
    """
    Cog support server manager
    """

    def __init__(self, bot: Red) -> None:
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(None, identifier=CONFIG_IDENTIFIER, cog_name=CONFIG_COG_NAME)
        self.config.register_global(schema_version=0)
        # {USER_ID: {REPO_NAME: {}}}
        self.config.init_custom("REPO", 2)
        self.config.register_custom("REPO")
        self.session = aiohttp.ClientSession()

    async def cog_check(self, ctx: commands.Context) -> bool:
        # commands in this cog should only run in Cog Support server
        return ctx.guild is not None and ctx.guild.id == COG_SUPPORT_SERVER_ID

    async def initialize(self) -> None:
        await self._config_migration()

    def cog_unload(self) -> None:
        if not self.session.closed:
            asyncio.create_task(self.session.close())

    __del__ = cog_unload

    async def _config_migration(self) -> None:
        schema_version = await self.config.schema_version()
        if schema_version == 0:
            await self._migrate_schema_0_to_1()
            await self.config.schema_version.set(1)

    async def _migrate_schema_0_to_1(self) -> None:
        # token migration
        maybe_token = await self.config.get_raw("token", default=None)
        if maybe_token is not None:
            api_tokens = await self.bot.get_shared_api_tokens("github")
            if not api_tokens.get("token", ""):
                await self.bot.set_shared_api_tokens("github", token=maybe_token)

        # repo data migration

        # old format
        service_urls = {
            "github": "https://github.com",
            "gitlab": "https://gitlab.com",
            "bitbucket": "https://bitbucket.org",
        }
        creator_levels = {
            "cog creator": CreatorLevel.COG_CREATOR,
            "senior cog creator": CreatorLevel.SENIOR_COG_CREATOR,
        }

        members = await self.config.all_members()
        # this cog is only working in one guild anyway, so this works
        user_data = members.get(COG_SUPPORT_SERVER_ID)
        if user_data is None:
            return

        to_save: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for user_id, data in user_data.items():
            user_repos_to_save = to_save[str(user_id)] = {}
            repos = data["repos"]

            for repo_name, repo_data in repos.items():
                repo_url = "/".join(
                    (service_urls[repo_data["service"]], repo_data["username"], repo_name)
                )
                creator_level = creator_levels[repo_data["creator_level"]]

                repo = Repo(
                    bot=self.bot,
                    repo_name=repo_data["repository"],
                    repo_url=repo_url,
                    user_id=user_id,
                    creator_level=creator_level,
                    support_channel_id=repo_data["channel"] or None,
                )

                user_repos_to_save[repo_name] = repo.to_dict()

        await self.config.custom("REPO").set(to_save)
        await self.config.clear_all_members()

    async def get_all_repos_flattened(self) -> List[Repo]:
        all_users = await self.get_all_repos()
        return [repo for repos in all_users.values() for repo in repos]

    async def get_all_repos(self) -> Dict[int, List[Repo]]:
        return await Repo.from_config(self.bot)

    async def get_user_repos(self, user_id: int) -> List[Repo]:
        return await Repo.from_config(self.bot, user_id)

    async def get_repo(self, user_id: int, repo_name: str) -> Repo:
        return await Repo.from_config(self.bot, user_id, repo_name)

    @property
    def cog_support_guild(self):
        return self.bot.get_guild(COG_SUPPORT_SERVER_ID)

    @property
    def default_support_channel(self) -> discord.TextChannel:
        return self.bot.get_channel(OTHERCOGS_ID)

    @property
    def support_category_channel(self) -> discord.CategoryChannel:
        return self.bot.get_channel(V3_COG_SUPPORT_CATEGORY_ID)

    @property
    def cog_creator_role(self):
        return self.cog_support_guild.get_role(COG_CREATOR_ROLE_ID)

    @property
    def senior_cog_creator_role(self):
        return self.cog_support_guild.get_role(SENIOR_COG_CREATOR_ROLE_ID)

    @is_core_dev_or_qa()
    @commands.command()
    async def reposlist(self, ctx: commands.Context) -> None:
        """
        Show a list of all Cog Creators and their repos.
        """
        all_repos = await self.get_all_repos_flattened()
        total_pages = math.ceil(len(all_repos) / 9)
        pages = []
        for idx, repo_group in enumerate(grouper(all_repos, 9), 1):
            embed = discord.Embed(title="Repo list")
            for repo in repo_group:
                support_channel = (
                    None if repo.support_channel is None else repo.support_channel.mention
                )
                embed.add_field(
                    name=repo.name,
                    value=(
                        f"**Creator:**\n{repo.username}\n"
                        f"**Creator level:**\n{repo.creator_level!s}\n"
                        f"**Support channel:**\n{support_channel}\n"
                        f"[Repo link]({repo.url})"
                    ),
                )
            embed.set_footer(text=f"Page {idx}/{total_pages}")
            pages.append(embed)
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @is_core_dev_or_qa()
    @commands.command()
    async def addcreator(
        self,
        ctx: commands.Context,
        member: discord.Member,
        url: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """
        Register a new cog creator

        `url` should be a link to the repository
        You can pass a channel if one already exists.
        """
        # XXX: hmm, this limitation doesn't make *that* much sense,
        # XXX: but some data would need to be moved elsewhere if I were to remove this
        if await self.config.custom("REPO", str(member.id)).all():
            await ctx.send("That user has already been marked as a cog creator")
            return

        service, username, repo_name = self.parse_url(url)
        async with self.session.get(url, allow_redirects=False) as resp:
            if service.lower() == "gitlab" and resp.status == 302 or resp.status == 404:
                await ctx.send("Repo with the given URL doesn't exist.")
                return

        repo = Repo(
            bot=self.bot,
            repo_name=repo_name,
            repo_url=url,
            user_id=member.id,
            support_channel_id=None if channel is None else channel.id,
        )

        if repo.support_channel_id is None:
            channel_name = f"support_{repo.name.lower()}"
            for channel in ctx.guild.text_channels:
                if channel.name == channel_name:
                    break
            else:
                channel = None
            repo.support_channel = channel

        await repo.save()
        await member.add_roles(self.cog_creator_role)
        await ctx.send(f"Done. {member.mention} is now a cog creator!")

    @is_core_dev_or_qa()
    @commands.command()
    async def grantsupport(
        self,
        ctx: commands.Context,
        member: discord.Member,
        repo: Repo,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """
        Grants this user a support channel. Must already be a cog creator
        """
        if repo.support_channel is not None:
            await ctx.send("It appears a channel already exists for that repo!")
            return

        await self._grant_support_channel(ctx, member, repo, channel)

    @is_core_dev_or_qa()
    @commands.command()
    async def makesenior(self, ctx: commands.Context, member: discord.Member, repo: Repo) -> None:
        """
        Makes this user a senior cog creator

        This command will also make a support channel for the given cog creator.
        """
        if repo.support_channel is None:
            await self._grant_support_channel(ctx, member, repo)
        repo.creator_level = CreatorLevel.SENIOR_COG_CREATOR
        await repo.save()
        await member.add_roles(self.senior_cog_creator_role)
        await ctx.send(f"Done. {member.mention} is now senior cog creator!")

    @is_senior_cog_creator()
    @commands.command()
    async def makeannouncement(
        self, ctx: commands.Context, repo: str, mention_users: bool = False, *, message: str
    ) -> None:
        """
        Make an announcement in your repo's news channel.

        repo needs to be the name of your repo

        mention_users, if set to True, will mention everyone when making the announcement

        This command doesn't do anything right now.
        """
        pass

    @is_core_dev_or_qa()
    @commands.command()
    async def makechannellist(self, ctx: commands.Context) -> None:
        """
        Make a list of all support channels
        """
        all_users = await self.get_all_repos()
        embeds: List[discord.Embed] = []
        for repos in all_users.values():
            for repo in repos:
                embed = discord.Embed(title=repo.name)
                embed.url = repo.url
                embed.set_author(
                    name=f"{repo.username} - {repo.creator_level!s}",
                    icon_url=discord.Embed.Empty if repo.user is None else repo.user.avatar_url,
                )
                if repo.support_channel is not None:
                    support_channel = repo.support_channel.mention
                else:
                    support_channel = self.default_support_channel.mention
                embed.add_field(name="Support channel", value=support_channel, inline=False)
                embeds.append(embed)

        webhook = await self._get_webhook(ctx.channel)
        if webhook is not None:
            for embed_group in grouper(embeds, 10):
                await webhook.send(embeds=embed_group)
        else:
            for embed in embeds:
                await ctx.send(embed=embed)
        await ctx.message.delete()

    async def _grant_support_channel(
        self,
        ctx: commands.Context,
        member: discord.Member,
        repo: Repo,
        channel: Optional[discord.TextChannel] = None,
    ):
        if channel is not None:
            if channel.category != self.support_category_channel:
                await channel.edit(
                    category=self.support_category_channel,
                    reason="Moving channel to V3 support category",
                )
            repo.support_channel = channel
            await repo.save()
            await ctx.send(
                f"Support channel for {repo.name} from {repo.username} set to {channel.mention}."
            )
            return

        channel_name = f"support_{repo.name.lower()}"
        for channel in ctx.guild.text_channels:
            if channel.name == channel_name:
                break
        else:
            channel = None

        if channel is not None:
            if channel.category != self.support_category_channel:
                await channel.edit(
                    category=self.support_category_channel,
                    reason="Moving channel to V3 support category",
                )
            msg = f"Existing channel ({channel.mention}) moved to the V3 support category."
        else:
            channel = await self.add_textchannel(
                channel_name, ctx.guild, member, self.support_category_channel
            )
            msg = f"{channel.mention} has been created!"
        repo.support_channel = channel
        await repo.save()
        await ctx.send(msg)

    async def _get_webhook(self, channel: discord.TextChannel) -> Optional[discord.Webhook]:
        guild = channel.guild
        if not channel.permissions_for(guild.me).manage_webhooks:
            return None
        try:
            webhooks = await channel.webhooks()
        except discord.Forbidden:
            return None
        for webhook in webhooks:
            if webhook.name == "Cog Support channel guide":
                break
        else:
            webhook = await channel.create_webhook(
                name="Cog Support channel guide",
                avatar=await guild.icon_url.read(),
                reason="Generating channel list",
            )
        return webhook

    async def add_textchannel(
        self,
        name: str,
        guild: discord.Guild,
        owner: discord.Member,
        category: discord.CategoryChannel,
    ) -> discord.TextChannel:
        overwrites = {
            owner: discord.PermissionOverwrite(
                manage_messages=True, manage_roles=True, manage_webhooks=True, manage_channels=True
            ),
        }

        # try to put the channel on proper position by assuming the channel list is alphabetical
        if category.channels:
            for channel in category.channels:
                if channel.name > name:
                    position = channel.position - 1
                    break
            else:
                position = category.channels[-1].position
        else:
            position = None

        return await guild.create_text_channel(
            name,
            overwrites=overwrites,
            category=category,
            position=position,
            reason=f"Adding a V3 cog support channel for {owner.name}",
        )

    def parse_url(self, url: str) -> Tuple[str, str, str]:
        parsed = yarl.URL(url)

        assert isinstance(parsed.host, str), "mypy"
        service = parsed.host.rsplit(".", maxsplit=2)[-2]

        username, repository = parsed.parts[1:3]

        return service, username, repository
