
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowService(StrEnum):
    CALENDAR = "calendar"
    WEATHER = "weather"


# REVIEW: ActionWorkflow 和 weather_schedule.py 里的 WeatherScheduleState 有相同的接口
# (current_action, has_next_action, user_chat_id, actions, index, results)
# 但没有共享基类或 Protocol。workflows.py 到处用 isinstance() 分支:
#   if isinstance(workflow, WeatherScheduleState): ...
#   if isinstance(workflow, ActionWorkflow): ...
# AI 生成代码倾向于"每个场景一个类"而不是抽象共性。
# 应该定义一个 Protocol 或 ABC 让两者共享接口，消除 isinstance 检查。
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
