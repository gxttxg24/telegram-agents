from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..telegram.utils import normalize_username


@dataclass(frozen=True)
class BotIdentity:
    profile: str
    token: str
    username: str


@dataclass
class BotPool:
    bots: dict[str, BotIdentity]

    @classmethod
    def from_bot_data(cls, bot_data: dict[str, Any]) -> BotPool:
        tokens: dict[str, str] = bot_data.get("bot_tokens", {})
        usernames: dict[str, str] = bot_data.get("bot_peers", {})
        bots = {
            profile.upper(): BotIdentity(
                profile=profile.upper(),
                token=token,
                username=normalize_username(usernames.get(profile.upper(), profile)),
            )
            for profile, token in tokens.items()
            if token
        }
        return cls(bots)

    def get(self, profile: str) -> BotIdentity | None:
        return self.bots.get(profile.strip().upper())


@dataclass(frozen=True)
class RoleAssignment:
    role_profiles: dict[str, str]

    @classmethod
    def from_bot_data(cls, bot_data: dict[str, Any]) -> RoleAssignment:
        raw = bot_data.get("expedition_role_profiles", {})
        return cls({str(role): str(profile).upper() for role, profile in raw.items()})

    def profile_for_role(self, role_id: str) -> str | None:
        return self.role_profiles.get(role_id.strip().casefold())
