from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .actions import ActionType, StageAction
from .models import WorldState


class ActionCategory(StrEnum):
    ORDINARY_ACTION = "ordinary_action"
    MINOR_PIVOT = "minor_pivot"
    MAJOR_PIVOT = "major_pivot"
    WORLD_RULE_CHALLENGE = "world_rule_challenge"
    DANGEROUS_ABSURD_PIVOT = "dangerous_absurd_pivot"
    CONCEPTUAL_ERROR = "conceptual_error"
    EXIT_OR_PAUSE = "exit_or_pause"


class ResponseStrategy(StrEnum):
    YES_AND = "yes_and"
    YES_BUT = "yes_but"
    NO_BUT = "no_but"
    EXPLAIN_THEN_OFFER = "explain_then_offer"


@dataclass(frozen=True)
class CompiledAction:
    raw_text: str
    category: ActionCategory
    strategy: ResponseStrategy
    action: StageAction
    goal: str = ""
    method: str = ""
    objects: list[str] = field(default_factory=list)
    safety_note: str = ""
    addressed_role: str = ""


def compile_user_action(
    state: WorldState,
    user_text: str,
    *,
    addressed_role: str = "",
) -> CompiledAction:
    text = user_text.strip()
    normalized = text.casefold()
    mentioned_role = addressed_role or _mentioned_role(normalized)

    if _has_any(normalized, "wait", "pause", "stop", "hold on", "等等", "暂停", "停", "改主意"):
        return CompiledAction(
            raw_text=text,
            category=ActionCategory.EXIT_OR_PAUSE,
            strategy=ResponseStrategy.YES_AND,
            action=StageAction(ActionType.INTERRUPT),
            goal="pause the expedition stage",
            addressed_role=mentioned_role,
        )

    if _has_any(
        normalized,
        "methane",
        "marsh gas",
        "explode",
        "explosion",
        "沼气",
        "爆炸",
        "引爆",
    ) and _has_any(
        normalized,
        "heaven",
        "sky",
        "cloud",
        "up",
        "上天",
        "天堂",
        "云",
    ):
        return CompiledAction(
            raw_text=text,
            category=ActionCategory.DANGEROUS_ABSURD_PIVOT,
            strategy=ResponseStrategy.NO_BUT,
            action=StageAction(ActionType.MOVE_LOCATION, target="cloud_wetland"),
            goal="explore a new high-altitude area safely",
            method="rewrite explosion into controlled marsh-spirit lift",
            objects=["marsh gas", "cloud wetland"],
            safety_note="Do not provide or encourage real explosion instructions.",
            addressed_role=mentioned_role,
        )

    if _looks_like_symbol_water_error(normalized):
        return CompiledAction(
            raw_text=text,
            category=ActionCategory.CONCEPTUAL_ERROR,
            strategy=ResponseStrategy.EXPLAIN_THEN_OFFER,
            action=StageAction(ActionType.CUSTOM, target="rune_water_alternatives"),
            goal="find water safely",
            method="explain symbols are not matter, then offer world-valid alternatives",
            objects=["H", "O", "water"],
            addressed_role=mentioned_role,
        )

    if _has_any(
        normalized,
        "computer",
        "chatgpt",
        "analyse",
        "analyze",
        "analysis",
        "ppt",
        "mentor",
        "report",
        "presentation",
        "电脑",
        "报告",
        "导师",
        "分析",
        "场景",
    ):
        return CompiledAction(
            raw_text=text,
            category=ActionCategory.MAJOR_PIVOT,
            strategy=ResponseStrategy.YES_BUT,
            action=StageAction(ActionType.GENERATE_REPORT_OUTLINE, target="field_report"),
            goal="turn the expedition evidence into a field analysis",
            method="reframe current clues as research material",
            objects=["field report", "scene analysis"],
            addressed_role=mentioned_role,
        )

    if mentioned_role:
        return CompiledAction(
            raw_text=text,
            category=ActionCategory.ORDINARY_ACTION,
            strategy=ResponseStrategy.YES_AND,
            action=StageAction(ActionType.ASK_ACTOR, target=mentioned_role),
            goal=f"talk to {mentioned_role}",
            addressed_role=mentioned_role,
        )

    if _has_any(normalized, "mori", "scholar", "ask", "学者", "询问", "问"):
        return CompiledAction(
            raw_text=text,
            category=ActionCategory.ORDINARY_ACTION,
            strategy=ResponseStrategy.YES_AND,
            action=StageAction(ActionType.ASK_ACTOR, target="scholar"),
            goal="ask the scholar",
            addressed_role="scholar",
        )

    return CompiledAction(
        raw_text=text,
        category=ActionCategory.ORDINARY_ACTION,
        strategy=ResponseStrategy.YES_AND,
        action=StageAction(ActionType.CUSTOM),
        goal="continue the field investigation",
        addressed_role=mentioned_role,
    )


def compiled_from_stage_action(action: StageAction) -> CompiledAction:
    return CompiledAction(
        raw_text=action.semantic_key,
        category=ActionCategory.ORDINARY_ACTION,
        strategy=ResponseStrategy.YES_AND,
        action=action,
        goal="resolve a controlled button action",
    )


def _looks_like_symbol_water_error(normalized: str) -> bool:
    mentions_symbols = "h" in normalized and "o" in normalized
    return mentions_symbols and _has_any(normalized, "water", "desert", "水", "沙漠")


def _has_any(value: str, *needles: str) -> bool:
    return any(needle in value for needle in needles)


def _mentioned_role(normalized: str) -> str:
    role_aliases = {
        "guide": ("ailo", "guide"),
        "scholar": ("mori", "scholar"),
        "scout": ("raven", "scout"),
        "log": ("pip", "recorder", "logger"),
        "mentor": ("serena", "mentor"),
    }
    for role_id, aliases in role_aliases.items():
        if _has_any(normalized, *aliases):
            return role_id
    return ""
