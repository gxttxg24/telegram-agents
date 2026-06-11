from __future__ import annotations

from typing import Any

from .compiler import CompiledAction
from .models import StageMessage, WorldState


ALLOWED_KNOWLEDGE_SOURCES = {
    "observed",
    "deduced",
    "remembered",
    "user",
    "world_rule",
}


def ensure_knowledge_ledger(state: WorldState) -> dict[str, Any]:
    ledger = state.flags.get("knowledge_ledger")
    if isinstance(ledger, dict):
        return ledger

    ledger = {
        "current_location": state.world_pack.location,
        "current_action": "",
        "facts": [
            {"text": clue, "source": "initial_clue", "turn_number": 0}
            for clue in state.clues
        ],
        "discoveries": [],
        "world_rules": [
            {"text": rule, "source": "world_pack", "turn_number": 0}
            for rule in state.world_pack.rules[:6]
        ],
        "referenced_facts": [],
    }
    state.flags["knowledge_ledger"] = ledger
    return ledger


def record_current_action(state: WorldState, compiled: CompiledAction) -> None:
    ledger = ensure_knowledge_ledger(state)
    ledger["current_action"] = compiled.raw_text or compiled.action.semantic_key


def knowledge_snapshot(state: WorldState) -> dict[str, Any]:
    ledger = ensure_knowledge_ledger(state)
    return {
        "current_location": ledger.get("current_location") or state.world_pack.location,
        "current_action": ledger.get("current_action", ""),
        "known_facts": _texts(ledger.get("facts"), limit=12),
        "discoveries": _texts(ledger.get("discoveries"), limit=8),
        "world_rules": _texts(ledger.get("world_rules"), limit=8),
    }


def apply_plan_knowledge(
    state: WorldState,
    plan: dict[str, Any],
    compiled: CompiledAction,
    messages: list[StageMessage],
) -> list[str]:
    ledger = ensure_knowledge_ledger(state)
    _record_fact_references(state, plan)

    location = _clean_text(plan.get("location_update"), max_chars=100)
    if location:
        ledger["current_location"] = location
        state.world_pack.location = location
        state.record_event("location_update", location, source="llm_planner")

    accepted: list[str] = []
    for item in _raw_knowledge_items(plan):
        accepted_text = _accept_knowledge_item(state, item, compiled, messages)
        if accepted_text:
            accepted.append(accepted_text)
    return accepted


def knowledge_notice_message(state: WorldState, accepted: list[str], epoch: int) -> StageMessage | None:
    if not accepted:
        return None
    text = _notice_text(state, accepted)
    return StageMessage(
        speaker_role_id="log",
        text=text,
        intent="record_new_knowledge",
        epoch=epoch,
    )


def _accept_knowledge_item(
    state: WorldState,
    item: dict[str, Any],
    compiled: CompiledAction,
    messages: list[StageMessage],
) -> str:
    ledger = ensure_knowledge_ledger(state)
    text = _clean_text(item.get("text"), max_chars=160)
    source = _clean_text(item.get("source"), max_chars=30).casefold()
    if not text or source not in ALLOWED_KNOWLEDGE_SOURCES:
        return ""

    because = _clean_list(item.get("because"), max_items=4, max_chars=120)
    if source in {"deduced", "remembered", "world_rule"} and not because:
        _reject(state, text, "missing_because")
        return ""
    if because and not _because_is_supported(state, because, compiled, messages):
        _reject(state, text, "unsupported_because", because=because)
        return ""

    target = "world_rules" if source == "world_rule" else "discoveries"
    if _already_known(ledger, text):
        return ""

    entry = {
        "text": text,
        "source": source,
        "because": because,
        "turn_number": state.turn_number,
    }
    ledger[target].append(entry)
    ledger["facts"].append(entry)
    state.record_event("knowledge_added", text, source=source, because=because)
    if source in {"observed", "deduced"} and text not in state.clues:
        state.clues.append(text)
    return text


def _record_fact_references(state: WorldState, plan: dict[str, Any]) -> None:
    references = _clean_list(plan.get("facts_referenced"), max_items=6, max_chars=120)
    if not references:
        return
    ledger = ensure_knowledge_ledger(state)
    accepted: list[str] = []
    for reference in references:
        if _text_supported_by_ledger(state, reference):
            accepted.append(reference)
    if accepted:
        ledger["referenced_facts"].extend(accepted)
        state.record_event("facts_referenced", "; ".join(accepted), source="llm_planner")


def _raw_knowledge_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("new_knowledge")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)][:5]


def _because_is_supported(
    state: WorldState,
    because: list[str],
    compiled: CompiledAction,
    messages: list[StageMessage],
) -> bool:
    context = _supporting_context(state, compiled, messages)
    return all(_has_support(reason, context) for reason in because)


def _text_supported_by_ledger(state: WorldState, text: str) -> bool:
    ledger = ensure_knowledge_ledger(state)
    context = [
        state.scene,
        state.world_pack.location,
        *_texts(ledger.get("facts"), limit=40),
        *_texts(ledger.get("world_rules"), limit=20),
    ]
    return _has_support(text, context)


def _supporting_context(
    state: WorldState,
    compiled: CompiledAction,
    messages: list[StageMessage],
) -> list[str]:
    ledger = ensure_knowledge_ledger(state)
    return [
        state.scene,
        state.world_pack.location,
        compiled.raw_text,
        compiled.action.semantic_key,
        *state.clues,
        *[message.text for message in messages],
        *_texts(ledger.get("facts"), limit=40),
        *_texts(ledger.get("world_rules"), limit=20),
    ]


def _has_support(text: str, context: list[str]) -> bool:
    normalized = text.casefold()
    for item in context:
        candidate = item.casefold()
        if normalized and normalized in candidate:
            return True
        if candidate and candidate in normalized:
            return True
        if len(_token_overlap(normalized, candidate)) >= 2:
            return True
    return False


def _token_overlap(left: str, right: str) -> set[str]:
    return _tokens(left) & _tokens(right)


def _tokens(text: str) -> set[str]:
    ascii_tokens = {
        token
        for token in "".join(char if char.isalnum() else " " for char in text).split()
        if len(token) >= 3
    }
    cjk_tokens = {char for char in text if "\u4e00" <= char <= "\u9fff"}
    return ascii_tokens | cjk_tokens


def _texts(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    texts: list[str] = []
    for item in value[-limit:]:
        if isinstance(item, dict):
            text = _clean_text(item.get("text"), max_chars=180)
        else:
            text = _clean_text(item, max_chars=180)
        if text:
            texts.append(text)
    return texts


def _already_known(ledger: dict[str, Any], text: str) -> bool:
    normalized = text.casefold()
    return normalized in {item.casefold() for item in _texts(ledger.get("facts"), limit=100)}


def _notice_text(state: WorldState, accepted: list[str]) -> str:
    language = state.flags.get("language")
    first = accepted[0]
    if language == "zh":
        if len(accepted) == 1:
            return f"新发现：{first}"
        return "新发现：" + "；".join(accepted[:3])
    if len(accepted) == 1:
        return f"New finding: {first}"
    return "New findings: " + "; ".join(accepted[:3])


def _reject(state: WorldState, text: str, reason: str, **data: Any) -> None:
    state.record_event("knowledge_rejected", text, reason=reason, **data)


def _clean_text(value: Any, *, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.strip().split())
    return cleaned[:max_chars]


def _clean_list(value: Any, *, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(item, max_chars=max_chars)
        if text:
            cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned
