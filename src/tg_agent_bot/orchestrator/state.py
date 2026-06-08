
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowService(StrEnum):
    CALENDAR = "calendar"
    WEATHER = "weather"


@dataclass
class ActionWorkflow:
    service: WorkflowService
    user_chat_id: int
    user_text: str
    actions: list[dict[str, Any]]
    index: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    goal: str = "forecast"

    @classmethod
    def calendar(
        cls,
        *,
        user_chat_id: int,
        user_text: str,
        actions: list[dict[str, Any]],
    ) -> ActionWorkflow:
        return cls(
            service=WorkflowService.CALENDAR,
            user_chat_id=user_chat_id,
            user_text=user_text,
            actions=actions,
        )

    @classmethod
    def weather(
        cls,
        *,
        user_chat_id: int,
        user_text: str,
        goal: str,
        actions: list[dict[str, Any]],
    ) -> ActionWorkflow:
        return cls(
            service=WorkflowService.WEATHER,
            user_chat_id=user_chat_id,
            user_text=user_text,
            goal=goal,
            actions=actions,
        )

    def current_action(self) -> dict[str, Any]:
        return dict(self.actions[self.index])

    def append_result(self, payload: dict[str, Any]) -> None:
        self.results.append(payload)

    def has_next_action(self) -> bool:
        return self.index < len(self.actions) - 1

    def advance(self) -> None:
        self.index += 1

ChatContext = dict[int, list[dict[str, Any]]]
