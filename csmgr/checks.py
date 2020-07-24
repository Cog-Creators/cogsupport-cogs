from redbot.core import commands

from .discord_ids import (
    COG_SUPPORT_SERVER_ID,
    CORE_DEV_ROLE_ID,
    QA_ROLE_ID,
    SENIOR_COG_CREATOR_ROLE_ID,
)


def is_cog_support_server():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.guild.id == COG_SUPPORT_SERVER_ID

    return commands.check(predicate)


def is_core_dev_or_qa():
    async def predicate(ctx: commands.Context) -> bool:
        return (
            ctx.guild.get_role(CORE_DEV_ROLE_ID) in ctx.author.roles
            or ctx.guild.get_role(QA_ROLE_ID) in ctx.author.roles
        )

    return commands.check(predicate)


def is_senior_cog_creator():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.guild.get_role(SENIOR_COG_CREATOR_ROLE_ID) in ctx.author.roles

    return commands.check(predicate)
