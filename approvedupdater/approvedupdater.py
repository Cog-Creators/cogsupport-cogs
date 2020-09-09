import discord
import aiohttp
import asyncio
from redbot.core import commands
from redbot.core import checks
from redbot.core import Config
import errno
from io import StringIO
import time


IX_PROTOCOL = 1
CC_INDEX_LINK = f"https://raw.githubusercontent.com/Cog-Creators/Red-Index/master/index/{IX_PROTOCOL}-min.json"


class Repo:
	def __init__(self, url: str, raw_data: dict):
		self.url = url
		self.approved = 'approved' == raw_data.get("rx_category", "unapproved")
		self.author = raw_data.get("author", ["Unknown"])
		self.description = raw_data.get("description", "")
		self.short = raw_data.get("short", "")
		self.name = raw_data.get("name", "Unknown")
		self.branch = raw_data.get("rx_branch", "")
		self.cogs = []
		if isinstance(raw_data["rx_cogs"], dict):
			for cog_name, cog_raw in raw_data["rx_cogs"].items():
				if cog_raw.get("hidden", False) or cog_raw.get("disabled", False):
					continue
				self.cogs.append(Cog(cog_name, self, cog_raw))
		else:
			for data in raw_data["rx_cogs"]:
				self.cogs.append(Cog(data['name'], self, data))
	
	def to_raw(self):
		result = vars(self).copy()
		cogs = []
		for c in result['cogs']:
			c = vars(c).copy()
			c.pop('repo', None)
			cogs.append(c)
		del result['cogs']
		result['rx_cogs'] = cogs
		return result
		
class Cog:
	def __init__(self, name: str, repo: Repo, raw_data: dict):
		self.name = name
		self.author = raw_data.get("author", ["Unknown"])
		self.description = raw_data.get("description", "")
		self.short = raw_data.get("short", "")
		self.hidden = False
		self.disabled = False
		self.repo = repo


class ApprovedUpdater(commands.Cog):
	"""
	Warns when the approved repository list needs to be updated.
	
	Most of the code stolen from TrustyJAID.
	"""
	
	def __init__(self, bot):
		self.bot = bot
		self.config = Config.get_conf(self, identifier=145519400223506432)
		self.config.register_global(
			lastRaw = []
		)
		self.last_check = time.time()
		
	
	@commands.mod()
	@commands.group()
	async def aru(self, ctx):
		"""Group command for Approved Repository Updater."""
		pass
	
	@aru.command()
	async def get(self, ctx):
		"""Get the string needed to update the approved repository list."""
		async with ctx.typing():
			repos = await self._get_repos()
			msg = await self._build_string(repos)
		file = StringIO(msg)
		file.name = 'result.txt'
		await ctx.send(file=discord.File(file))
		self.last_check = time.time()
		await self.config.last_string.set(msg)
	
	async def _get_repos(self):
		"""Get the Repo objects of approved repos."""
		repos = []
		async with aiohttp.ClientSession() as session:
			async with session.get(CC_INDEX_LINK) as r:
				if r.status != 200:
					raise RuntimeError(f'Could not fetch index. HTTP code: {r.status}')
				raw = await r.json(content_type=None)
		for url, data in raw.items():
			repos.append(Repo(url, data))
		return [r for r in repos if r.approved]
	
	async def _build_string(self, repos: list):
		"""Build the cogboard string from a list of Repos."""
		master = ''
		for repo in repos:
			master += f'_____________________________\n**{repo.name}**\nRepo Link: {repo.url}\n'
			if repo.branch:
				master += f'Branch: {repo.branch}\n'
			master += '\n'
			for cog in repo.cogs:
				master += f'+ {cog.name}: {cog.short}\n'
			master += '\n'
		return master

	async def _check_changes(self, new: list):
		result = {}
		
		old = await self.config.lastRaw()
		if old == [r.to_raw() for r in new]:
			return result
		old = [Repo(r['url'], r) for r in old]
		
		old_repos = set(r.url for r in old)
		new_repos = set(r.url for r in new)
		sum_repos = old_repos & new_repos
		old_repos -= sum_repos
		new_repos -= sum_repos
		
		result['rem_cogs'] = {}
		result['add_cogs'] = {}
		
		if old_repos:
			result['rem_repos'] = []
			for r in old_repos:
				repo = [x for x in old if x.url == r][0]
				result['rem_repos'].append(repo)
				result['rem_cogs'][repo] = repo.cogs
		if new_repos:
			result['add_repos'] = []
			for r in new_repos:
				repo = [x for x in new if x.url == r][0]
				result['add_repos'].append(repo)
				result['add_cogs'][repo] = repo.cogs
		
		for new_repo in new:
			#new repo, already handled
			if new_repo.url not in sum_repos:
				continue
			old_repo = [x for x in old if x.url == new_repo.url][0]
			
			old_cogs = set(r.name for r in old_repo.cogs)
			new_cogs = set(r.name for r in new_repo.cogs)
			sum_cogs = old_cogs & new_cogs
			old_cogs -= sum_cogs
			new_cogs -= sum_cogs
			
			if old_cogs:
				result['rem_cogs'][new_repo] = []
				for c in old_cogs:
					cog = [x for x in old_repo.cogs if x.name == c][0]
					result['rem_cogs'][new_repo].append(cog)
			if new_cogs:
				result['add_cogs'][new_repo] = []
				for c in new_cogs:
					cog = [x for x in new_repo.cogs if x.name == c][0]
					result['add_cogs'][new_repo].append(cog)
				
		if not result['rem_cogs']:
			del result['rem_cogs']
		if not result['add_cogs']:
			del result['add_cogs']
		
		return result
	
	@commands.Cog.listener()
	async def on_message(self, message):
		if time.time() < self.last_check + 3600:
			return
		self.last_check = time.time()
		ts = lambda: time.strftime('%I:%M:%S %p', time.localtime())
		print(f'[{ts()}] [ApprovedUpdater] Started check.')
		repos = await self._get_repos()
		changes = await self._check_changes(repos)
		print(f'[{ts()}] [ApprovedUpdater] Finished check. Took {round(time.time() - self.last_check, 2)} seconds.')
		if not changes:
			return
		last = await self.config.lastRaw.set([r.to_raw() for r in repos])
		diff = ''
		if 'add_repos' in changes:
			diff += '\nAdded repos\n-----------\n'
			for repo in changes['add_repos']:
				diff += f'+ {repo.name} - {repo.short}\n'
		if 'rem_repos' in changes:
			diff += '\nRemoved repos\n-------------\n'
			for repo in changes['rem_repos']:
				diff += f'- {repo.name} - {repo.short}\n'
		if 'add_cogs' in changes:
			diff += '\nAdded cogs\n----------\n'
			for repo in changes['add_cogs']:
				diff += f'{repo.name}:\n'
				for cog in changes['add_cogs'][repo]:
					diff += f'+ {cog.name} - {cog.short}\n'
		if 'rem_cogs' in changes:
			diff += '\nRemoved cogs\n------------\n'
			for repo in changes['rem_cogs']:
				diff += f'{repo.name}:\n'
				for cog in changes['rem_cogs'][repo]:
					diff += f'- {cog.name} - {cog.short}\n'

		channel = self.bot.get_channel(598626368665813005)
		print(f'[{ts()}] [ApprovedUpdater] Update required!\n')
		print(diff)
		diff = diff[:1954]
		await channel.send(f'The cogboard needs to be updated!\n```diff\n{diff}```'[:2000])
		cog_server_channel = self.bot.get_channel(723262416766500937)
		m = await cog_server_channel.send(f'```diff\n{diff}```'[:2000])
		await m.publish()
