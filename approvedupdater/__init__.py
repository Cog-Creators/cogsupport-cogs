from .approvedupdater import ApprovedUpdater

async def setup(bot):
	await bot.add_cog(ApprovedUpdater(bot))
