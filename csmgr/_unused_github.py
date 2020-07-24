"""
Stuff here is no longer used.
"""

import logging
from typing import Any, Dict, Optional, Mapping

import aiohttp
from redbot.core.bot import Red
from redbot.core import commands

GH_API = "https://api.github.com/graphql"

log = logging.getLogger("red.cogsupport-cogs.csmgr._unused")


class GitHubMixin:
    """
    This mixin contains things related to GitHub API.
    It is no longer used but if needed, it can easily be added back to the cog.
    """

    def __init__(self) -> None:
        # this should be put in ABC class if we will want to use this mixin again
        self.bot: Red
        self.session: aiohttp.ClientSession
        self.token: str  # assigned in initialize()

    async def initialize(self) -> None:
        self.token = await self._get_token()

    async def _get_token(self, api_tokens: Optional[Mapping[str, str]] = None) -> str:
        """Get GitHub token."""
        if api_tokens is None:
            api_tokens = await self.bot.get_shared_api_tokens("github")

        token = api_tokens.get("token", "")
        if not token:
            log.error("No valid token found")
        return token

    async def do_request(self, data: dict) -> Dict[str, Any]:
        async with self.session.post(
            GH_API, json=data, headers={"Authorization": f"Bearer {self.token}"}
        ) as r:
            resp = await r.json()
            return resp

    @commands.Cog.listener()
    async def on_red_api_tokens_update(
        self, service_name: str, api_tokens: Mapping[str, str]
    ) -> None:
        """Update GitHub token when `[p]set api` command is used."""
        if service_name != "github":
            return
        self.token = await self._get_token(api_tokens)
