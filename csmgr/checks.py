from redbot.core import commands

from .discord_ids import (
    ORG_MEMBER_ROLE_ID,
    SENIOR_COG_CREATOR_ROLE_ID,
)


def is_org_member():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.guild.get_role(ORG_MEMBER_ROLE_ID) in ctx.author.roles

    return commands.check(predicate)


def is_senior_cog_creator():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.guild.get_role(SENIOR_COG_CREATOR_ROLE_ID) in ctx.author.roles

    return commands.check(predicate)
