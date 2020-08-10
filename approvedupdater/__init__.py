from .approvedupdater import ApprovedUpdater

def setup(bot):
	bot.add_cog(ApprovedUpdater(bot))
