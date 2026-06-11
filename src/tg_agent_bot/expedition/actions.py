from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


CALLBACK_PREFIX = "expedition:action:"


class ActionType(StrEnum):
    OBSERVE_CLUE = "observe_clue"
    ASK_ACTOR = "ask_actor"
    ASSIST_ACTOR = "assist_actor"
    MOVE_LOCATION = "move_location"
    INTERRUPT = "interrupt"
    RESUME_OBJECTIVE = "resume_objective"
    GENERATE_REPORT_OUTLINE = "generate_report_outline"
    COLLECT_EVIDENCE = "collect_evidence"
    GENERATE_SUMMARY = "generate_summary"
    CHOOSE_PROPOSAL = "choose_proposal"
    CUSTOM = "custom"


@dataclass(frozen=True)
class StageAction:
    action_type: ActionType
    target: str = ""
    label: str = ""

    @property
    def semantic_key(self) -> str:
        if self.target:
            return f"{self.action_type.value}:{self.target}"
        return self.action_type.value

    def to_callback_data(self) -> str:
        return f"{CALLBACK_PREFIX}{self.semantic_key}"

    @classmethod
    def from_callback_data(cls, value: str) -> StageAction | None:
        if not value.startswith(CALLBACK_PREFIX):
            return None
        raw = value.removeprefix(CALLBACK_PREFIX)
        action_name, separator, target = raw.partition(":")
        try:
            action_type = ActionType(action_name)
        except ValueError:
            return None
        return cls(action_type=action_type, target=target if separator else "")


def action_for_button(label: str) -> StageAction:
    normalized = label.strip().casefold()
    if _has_any(
        normalized,
        "inspect",
        "check",
        "observe",
        "footprint",
        "clue",
        "足迹",
        "检查",
        "观察",
        "线索",
    ):
        return StageAction(ActionType.OBSERVE_CLUE, target="footprints", label=label)
    if _has_any(normalized, "ask", "mori", "scholar", "学者", "询问", "问"):
        return StageAction(ActionType.ASK_ACTOR, target="scholar", label=label)
    if _has_any(
        normalized,
        "choose",
        "proposal",
        "route",
        "plan",
        "采纳",
        "选择",
        "方案",
        "路线",
    ):
        return StageAction(ActionType.CHOOSE_PROPOSAL, target="synthesis", label=label)
    if _has_any(normalized, "raven", "scout", "send", "派", "侦察", "探路"):
        return StageAction(ActionType.ASSIST_ACTOR, target="scout", label=label)
    if _has_any(
        normalized,
        "watchtower",
        "tower",
        "go",
        "move",
        "瞭望塔",
        "前往",
        "移动",
        "深入",
        "继续",
    ):
        return StageAction(ActionType.MOVE_LOCATION, target="old_watchtower", label=label)
    if _has_any(normalized, "wait", "pause", "等待", "等等", "暂停", "停"):
        return StageAction(ActionType.INTERRUPT, label=label)
    if _has_any(normalized, "resume", "restore", "恢复", "继续原"):
        return StageAction(ActionType.RESUME_OBJECTIVE, label=label)
    if _has_any(normalized, "ppt", "outline", "report", "大纲", "报告"):
        return StageAction(ActionType.GENERATE_REPORT_OUTLINE, target="ppt_outline", label=label)
    if _has_any(normalized, "collect", "sample", "data", "采集", "样本", "数据"):
        return StageAction(ActionType.COLLECT_EVIDENCE, label=label)
    if _has_any(normalized, "summary", "摘要", "总结"):
        return StageAction(ActionType.GENERATE_SUMMARY, label=label)
    return StageAction(ActionType.CUSTOM, label=label)


def _has_any(value: str, *needles: str) -> bool:
    return any(needle in value for needle in needles)
