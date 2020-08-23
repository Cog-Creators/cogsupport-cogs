from typing import Optional

import discord
from redbot.core import commands


async def add_textchannel(
    ctx: commands.GuildContext,
    name: str,
    owner: discord.Member,
    category: discord.CategoryChannel,
) -> Optional[discord.TextChannel]:
    """
    Adds a text channel with given `owner` having all manage perms in it.

    This function doesn't raise and instead returns `None` if channel couldn't be created.

    This function provides feedback using `ctx.send()`.
    """
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

    try:
        if not category.permissions_for(ctx.guild.me).manage_channels:
            raise RuntimeError
        return await ctx.guild.create_text_channel(
            name,
            overwrites=overwrites,
            category=category,
            position=position,
            reason=f"Adding a V3 cog support channel for {owner.name}",
        )
    except (discord.Forbidden, RuntimeError):
        await ctx.send("I wasn't able to create support channel.")
        return None


async def get_webhook(channel: discord.TextChannel) -> Optional[discord.Webhook]:
    """
    Gets existing or creates new webhook for given channel
    or returns `None` if bot doesn't have proper permissions.
    """
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


async def safe_add_role(
    ctx: commands.GuildContext, member: discord.Member, role: discord.Role
) -> None:
    """
    Adds a role to given member without raising.

    This function provides feedback using `ctx.send()`.
    """
    try:
        if not ctx.me.guild_permissions.manage_roles:
            raise RuntimeError
        await member.add_roles(role)
    except (discord.Forbidden, RuntimeError):
        await ctx.send(f"I wasn't able to add {role.name} role.")


async def safe_remove_role(
    ctx: commands.Context, member: discord.Member, role: discord.Role
) -> None:
    """
    Removes a role from given member without raising.

    This function provides feedback using `ctx.send()`.
    """
    try:
        if not ctx.me.guild_permissions.manage_roles:
            raise RuntimeError
        await member.remove_roles(role)
    except (discord.Forbidden, RuntimeError):
        await ctx.send(f"I wasn't able to remove {role.name} role.")