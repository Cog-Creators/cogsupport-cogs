from redbot.core.bot import Red

from .csmgr import CSMgr


async def setup(bot: Red) -> None:
    cog = CSMgr(bot)
    await cog.initialize()
    bot.add_cog(cog)
