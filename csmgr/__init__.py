from .csmgr import CSMgr


def setup(bot):
    bot.add_cog(CSMgr(bot))