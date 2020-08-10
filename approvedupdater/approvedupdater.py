import discord
import aiohttp
import asyncio
import functools
from redbot.core import commands
from redbot.core import checks
from redbot.core import Config
from redbot.core.data_manager import cog_data_path
import git
import json
import os
import glob
import stat
import errno
from typing import List, Mapping
from dataclasses import dataclass
from io import StringIO
import time
import difflib
from shutil import rmtree

@dataclass
class InfoJson:
	author: List[str]
	description: str
	install_msg: str
	short: str
	name: str
	bot_version: List[int]
	hidden: bool
	disabled: bool
	required_cogs: Mapping[str, str]
	requirements: List[str]
	tags: List[str]
	type: str
	permissions: list
	min_python_version: list

	@classmethod
	def from_json(cls, data: dict):
		author = []
		description = ""
		install_msg = "Thanks for installing"
		short = "Thanks for installing"
		bot_version = [3, 0, 0]
		name = ""
		required_cogs = ()
		requirements = []
		tags = []
		hidden = False
		disabled = False
		type = "COG"
		permissions = []
		min_python_version = []
		if "author" in data:
			author = data["author"]
		if "description" in data:
			description = data["description"]
		if "install_msg" in data:
			install_msg = data["install_msg"]
		if "short" in data:
			short = data["short"]
		if "bot_version" in data:
			bot_version = data["bot_version"]
		if "name" in data:
			name = data["name"]
		if "required_cogs" in data:
			required_cogs = data["required_cogs"]
		if "requirements" in data:
			requirements = data["requirements"]
		if "tags" in data:
			tags = data["tags"]
		if "hidden" in data:
			hidden = data["hidden"]
		if "disabled" in data:
			disabled = data["disabled"]
		if "type" in data:
			type = data["type"]
		if "permissions" in data:
			permissions = data["permissions"]
		if "min_python_version" in data:
			min_python_version = data["min_python_version"]

		return cls(
			author,
			description,
			install_msg,
			short,
			name,
			bot_version,
			hidden,
			disabled,
			required_cogs,
			requirements,
			tags,
			type,
			permissions,
			min_python_version,
		)

class ApprovedUpdater(commands.Cog):
	"""
	Warns when the approved repository list needs to be updated.
	
	Most of the code stolen from TrustyJAID.
	"""
	
	def __init__(self, bot):
		self.bot = bot
		self.config = Config.get_conf(self, identifier=145519400223506432)
		self.config.register_global(
			last_string = '',
			repos = []
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
			msg = await self.build_string(ctx)
		file = StringIO(msg)
		file.name = 'result.txt'
		await ctx.send(file=discord.File(file))
		self.last_check = time.time()
		await self.config.last_string.set(msg)

	@aru.command()
	async def add(self, ctx, url, branch=None):
		"""Add a new repo."""
		async with self.config.repos() as repos:
			if url in (repo[0] for repo in repos):
				return await ctx.send('That repo has already been added.')
			repos.append([url, branch])
		await ctx.send('Added.')
	
	@aru.command()
	async def rem(self, ctx, url):
		"""Remove an existing repo."""
		async with self.config.repos() as repos:
			repo_links = [repo[0] for repo in repos]
			if url not in repo_links:
				return await ctx.send('That repo does not exist')
			index = repo_links.index(url)
			repos.remove(repos[index])
		await ctx.send('Removed.')
	
	@aru.command()
	async def list(self, ctx):
		"""List the current repos."""
		repos = await self.config.repos()
		msg = ''
		for repo in repos:
			msg += f'{repo[0]} {repo[1] if repo[1] else ""}\n'
		await ctx.send(f'```\n{msg}```')
	
	async def build_string(self, ctx=None):
		if ctx: #channel here is ONLY for error logging, do NOT use the cog server channel
			channel = ctx.channel
		else:
			channel = self.bot.get_channel(598626368665813005)
		master = ""
		PATH = cog_data_path(self) / 'temp'
		repo_list = await self.config.repos()
		if ctx:
			message = await ctx.send('Creating an updated approved repository list.')
			n = 0
		for repos in repo_list:
			repo_name = repos[0].split("/")[-1]
			if ctx:
				n += 1
				await message.edit(content=(
					'Creating an updated approved repository list.\n\n'
					f'Downloading **{repo_name}** ({n}/{len(repo_list)})'
				))
			try:
				if repos[1]:
					task = functools.partial(git.Git(PATH).clone, repos[0], branch=repos[1])
				else:
					task = functools.partial(git.Git(PATH).clone, repos[0])
				task = self.bot.loop.run_in_executor(None, task)
				repo_data = await asyncio.wait_for(task, timeout=180)
			except asyncio.TimeoutError:
				print(f'ApprovedUpdater timed out trying to download repo "{repo_name}"')
				await channel.send(f'ApprovedUpdater timed out trying to download repo `{repo_name}`')
			except git.exc.GitCommandError:
				pass
			except Exception as e:
				print(f'ApprovedUpdater errored trying to download repo "{repo_name}":\n{e}')
				await channel.send(f'ApprovedUpdater errored trying to download repo `{repo_name}`:\n`{e}`')
			await asyncio.sleep(0)
		def handleRemoveReadonly(func, path, exc):
			"""https://stackoverflow.com/questions/1213706/what-user-do-python-scripts-run-as-in-windows"""
			excvalue = exc[1]
			if func in (os.rmdir, os.unlink, os.remove) and excvalue.errno == errno.EACCES:
				os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
				func(path)
			else:
				raise
		if ctx:
			await message.edit(content=(
				'Creating an updated approved repository list.\n\n'
				'Building strings...'
			))
		for repo in repo_list:
			repo_name = repo[0].split("/")[-1]
			master += f"_____________________________\n**{repo_name}**\nRepo Link: {repo[0]}\n"
			if repo[1]:
				master += f'Branch: {repo[1]}\n'
			master += '\n'
			for cog_data in glob.glob(f"{PATH}/{repo_name}/**/info.json"):
				try:
					with open(cog_data, encoding='utf-8') as infile:
						data = json.loads(infile.read())
					cog = InfoJson.from_json(data)
					name = cog_data.split("\\")[-2]
					if not (cog.hidden or cog.disabled):
						master += f"+ {name}: {cog.short}\n"
					await asyncio.sleep(0)
				except json.decoder.JSONDecodeError as e:
					print(f'ApprovedUpdater errored trying to read a file.\n\nRepo: {repo_name}\nFile: {cog_data}\nError: {e}')
					await channel.send(f'ApprovedUpdater errored trying to read a file.\n\nRepo: `{repo_name}`\nFile: `{cog_data}`\nError: `{e}`')
			master += "\n"
			rmtree(PATH / repo_name, ignore_errors=False, onerror=handleRemoveReadonly)
		if ctx:
			await message.delete()
		return master
	
	@commands.Cog.listener()
	async def on_message(self, message):
		if time.time() < self.last_check + 3600:
			return
		self.last_check = time.time()
		ts = lambda: time.strftime('%I:%M:%S %p', time.localtime())
		print(f'[{ts()}] [ApprovedUpdater] Started check.')
		string = await self.build_string()
		print(f'[{ts()}] [ApprovedUpdater] Finished check. Took {round(time.time() - self.last_check, 2)} seconds.')
		last = await self.config.last_string()
		if string == last:
			return
		print()
		await self.config.last_string.set(string)
		diff = f'[{ts()}] [ApprovedUpdater] Update required!'
		print(diff)
		for line in difflib.unified_diff(last.split('\n'), string.split('\n')):
			diff += line + '\n'
		channel = self.bot.get_channel(598626368665813005)
		diff = diff[:1954]
		await channel.send(f'The cogboard needs to be updated!\n```diff\n{diff}```'[:2000])
		cog_server_channel = self.bot.get_channel(723262416766500937)
		await cog_server_channel.send(f'```diff\n{diff}```'[:2000])
			
