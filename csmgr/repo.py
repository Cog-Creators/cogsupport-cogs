from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union, overload

import discord
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core import commands

from .utils import static_property

CONFIG_COG_NAME = "CSMgr"
CONFIG_IDENTIFIER = 59595922


class CreatorLevel(Enum):
    COG_CREATOR = 1
    SENIOR_COG_CREATOR = 2

    def __str__(self) -> str:
        # pylint: disable=no-member
        return self.name.replace("_", " ").lower()

    @property
    def friendly_name(self) -> str:
        return str(self)


class Repo:
    """Cog Creator's repo"""

    def __init__(
        self,
        *,
        bot: Red,
        repo_name: str,
        repo_url: str,
        user_id: int,
        creator_level: CreatorLevel = CreatorLevel.COG_CREATOR,
        support_channel_id: Optional[int] = None,
    ) -> None:
        self.bot = bot

        self.name = repo_name
        self.url = repo_url

        self.user_id = user_id
        self.creator_level = creator_level
        self.support_channel_id = support_channel_id

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> Repo:
        """This converter needs the argument before itself to be `discord.Member`"""
        user = ctx.args[-1]
        try:
            return await cls.from_config(ctx.bot, user.id, argument)
        except KeyError:
            raise commands.BadArgument("Repo with this name doesn't exist for given member.")

    async def save(self) -> None:
        await self.config.custom("REPO", str(self.user_id), self.name).set(self.to_dict())

    @static_property
    def config() -> Config:  # type: ignore[misc]
        return Config.get_conf(None, identifier=CONFIG_IDENTIFIER, cog_name=CONFIG_COG_NAME)

    @property
    def support_channel(self) -> Optional[discord.TextChannel]:
        if self.support_channel_id:
            return self.bot.get_channel(self.support_channel_id)
        return None

    @support_channel.setter
    def support_channel(self, value: Optional[discord.TextChannel]) -> None:
        self.support_channel_id = None if value is None else value.id

    @property
    def user(self) -> Optional[discord.User]:
        return self.bot.get_user(self.user_id)

    @property
    def username(self) -> str:
        if self.user is None:
            return f"Creator unavailable ({self.user_id})"
        return self.user.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_url": self.url,
            "creator_level": self.creator_level.value,
            "support_channel_id": self.support_channel_id,
        }

    @classmethod
    def from_dict(cls, bot: Red, user_id: int, repo_name: str, data: Dict[str, Any]) -> Repo:
        return cls(
            bot=bot,
            user_id=user_id,
            repo_name=repo_name,
            repo_url=data["repo_url"],
            creator_level=CreatorLevel(data["creator_level"]),
            support_channel_id=data["support_channel_id"],
        )

    @overload
    @classmethod
    async def from_config(
        cls, bot: Red, user_id: None = ..., repo_name: None = ...
    ) -> Dict[int, List[Repo]]:
        ...

    @overload
    @classmethod
    async def from_config(cls, bot: Red, user_id: int, repo_name: None = ...) -> List[Repo]:
        ...

    @overload
    @classmethod
    async def from_config(cls, bot: Red, user_id: int, repo_name: str) -> Repo:
        ...

    @classmethod
    async def from_config(
        cls, bot: Red, user_id: Optional[int] = None, repo_name: Optional[str] = None,
    ) -> Union[Dict[int, List[Repo]], List[Repo], Repo]:
        if user_id is None:
            if repo_name is not None:
                raise ValueError("`repo_name` cant' be passed if `user_id` isn't.")

            all_users = await cls.config.custom("REPO").all()
            return {
                int(user_id): [
                    Repo.from_dict(bot, int(user_id), repo_name, data)
                    for repo_name, data in repos.items()
                ]
                for user_id, repos in all_users.items()
            }

        if repo_name is None:
            repos = await cls.config.custom("REPO", str(user_id)).all()
            return [
                Repo.from_dict(bot, user_id, repo_name, data) for repo_name, data in repos.items()
            ]

        repo_data = await cls.config.custom("REPO", str(user_id), repo_name).all()
        if not repo_data:
            raise KeyError("Repo with given name doesn't exist!")

        return Repo.from_dict(bot, user_id, repo_name, repo_data)
