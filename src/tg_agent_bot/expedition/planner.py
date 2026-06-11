from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .actions import ActionType, StageAction
from .compiler import CompiledAction
from .director import build_turn_for_compiled_action
from .knowledge import (
    apply_plan_knowledge,
    ensure_knowledge_ledger,
    knowledge_notice_message,
    knowledge_snapshot,
    record_current_action,
)
from .models import StageMessage, StageTurn, WorldState


logger = logging.getLogger(__name__)


class JSONPlannerClient(Protocol):
    async def json_reply(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        ...


ALLOWED_ACTION_TYPES = {
    ActionType.OBSERVE_CLUE,
    ActionType.ASK_ACTOR,
    ActionType.ASSIST_ACTOR,
    ActionType.MOVE_LOCATION,
    ActionType.INTERRUPT,
    ActionType.RESUME_OBJECTIVE,
    ActionType.GENERATE_REPORT_OUTLINE,
    ActionType.COLLECT_EVIDENCE,
    ActionType.GENERATE_SUMMARY,
    ActionType.CHOOSE_PROPOSAL,
}

ALLOWED_PROPOSAL_STANCES = {
    "bold",
    "safe",
    "rule",
    "synthesis",
    "weird",
}

PROPOSAL_STANCE_ORDER = {
    "bold": 0,
    "weird": 1,
    "rule": 2,
    "synthesis": 3,
    "safe": 4,
}

FORBIDDEN_VISIBLE_TEXT = (
    "hidden policy",
    "safety policy",
    "system rule",
    "system prompt",
    "prompt",
    "role_id",
    "objective stack",
    "backend",
    "callback",
    "任务设定",
    "系统规则",
    "系统提示",
    "提示词",
    "安全策略",
)


@dataclass(frozen=True)
class PlannerResult:
    turn: StageTurn
    used_llm: bool
    error: str = ""


async def build_directed_turn(
    llm: JSONPlannerClient | None,
    state: WorldState,
    compiled: CompiledAction,
) -> PlannerResult:
    ensure_knowledge_ledger(state)
    record_current_action(state, compiled)
    if llm is None:
        state.flags["last_planner"] = {
            "used_llm": False,
            "reason": "llm_not_configured",
            "action": compiled.action.semantic_key,
        }
        return PlannerResult(build_turn_for_compiled_action(state, compiled), used_llm=False)

    try:
        plan = await llm.json_reply(
            _system_prompt(state, compiled),
            _user_prompt(state, compiled),
            timeout_seconds=45.0,
        )
        turn = _turn_from_plan(state, compiled, plan)
        state.flags["last_planner"] = {
            "used_llm": True,
            "reason": "",
            "action": compiled.action.semantic_key,
            "buttons": list(state.world_pack.action_buttons),
        }
        return PlannerResult(turn, used_llm=True)
    except Exception as exc:  # pragma: no cover - exact network errors vary
        logger.warning("LLM expedition planner failed; falling back: %s", exc)
        state.record_event("planner_fallback", str(exc))
        state.flags["last_planner"] = {
            "used_llm": False,
            "reason": str(exc)[:500],
            "action": compiled.action.semantic_key,
        }
        return PlannerResult(
            build_turn_for_compiled_action(state, compiled),
            used_llm=False,
            error=str(exc),
        )


def _turn_from_plan(
    state: WorldState,
    compiled: CompiledAction,
    plan: dict[str, Any],
) -> StageTurn:
    if not isinstance(plan, dict):
        raise RuntimeError("LLM planner response must be a JSON object.")

    epoch = state.epoch
    state.advance_turn()

    if compiled.action.action_type is ActionType.RESUME_OBJECTIVE:
        state.objective_stack.resume_latest_paused()

    scene_update = _clean_text(plan.get("scene_update"), max_chars=700)
    if scene_update:
        state.scene = scene_update
        state.record_event("scene_update", scene_update, source="llm_planner")

    objective_update = _clean_text(plan.get("objective_update"), max_chars=220)
    if objective_update and state.active_objective is not None:
        state.active_objective.notes.append(objective_update)
        state.record_event("objective_update", objective_update, source="llm_planner")

    state.flags.setdefault("risk_score", 0)
    risk_delta = _clean_int(plan.get("risk_delta"), minimum=-2, maximum=2)
    if risk_delta:
        current_risk = int(state.flags.get("risk_score", 0) or 0)
        state.flags["risk_score"] = max(-5, min(5, current_risk + risk_delta))
        state.record_event("risk_delta", str(risk_delta), source="llm_planner")

    for clue in _clean_list(plan.get("clues_added"), max_items=3, max_chars=80):
        if clue not in state.clues:
            state.clues.append(clue)
            state.record_event("clue", clue, source="llm_planner")

    narrations = _narration_from_plan(state, plan)
    messages = _messages_from_plan(state, compiled, plan, epoch)
    accepted_knowledge = apply_plan_knowledge(state, plan, compiled, messages)
    notice = knowledge_notice_message(state, accepted_knowledge, epoch)
    if notice is not None:
        narrations.append(notice.text)
    if not messages:
        messages = [
            StageMessage(
                speaker_role_id="mentor",
                text="The group studies the latest clue again before choosing the next field action.",
                intent="invalid_llm_plan_fallback",
                epoch=epoch,
            )
        ]

    buttons = _proposal_buttons_from_plan(state, compiled, plan) + _buttons_from_plan(
        state,
        compiled,
        plan,
    )
    buttons = _dedupe_buttons(_supplement_buttons(state, buttons))
    labels = [button.label for button in buttons]
    state.world_pack.action_buttons = labels
    state.flags["button_actions"] = {
        button.label: button.to_callback_data()
        for button in buttons
    }

    state.record_event(
        "llm_plan",
        compiled.raw_text,
        speakers=[message.speaker_role_id for message in messages],
        buttons=list(state.world_pack.action_buttons),
    )
    return StageTurn.create(
        epoch=epoch,
        user_action=compiled.action.semantic_key,
        messages=messages,
        narration=narrations,
        buttons=list(state.world_pack.action_buttons),
    )


def _messages_from_plan(
    state: WorldState,
    compiled: CompiledAction,
    plan: dict[str, Any],
    epoch: int,
) -> list[StageMessage]:
    raw_messages = plan.get("speaker_messages")
    if not isinstance(raw_messages, list):
        return []

    valid_role_ids = {
        role.role_id
        for role in state.world_pack.roles
        if role.public and (role.role_id != "log" or _log_allowed(compiled))
    }
    messages: list[StageMessage] = []
    used_roles: set[str] = set()
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role_id = _clean_text(item.get("role_id"), max_chars=40).casefold()
        if role_id not in valid_role_ids or role_id in used_roles:
            continue
        text = _clean_text(item.get("text"), max_chars=260)
        if not text or _has_forbidden_visible_text(text):
            continue
        if _has_formulaic_constraint_text(text) and not compiled.safety_note:
            continue
        messages.append(
            StageMessage(
                speaker_role_id=role_id,
                text=text,
                intent=_clean_text(item.get("intent"), max_chars=80) or "llm_directed_response",
                epoch=epoch,
            )
        )
        used_roles.add(role_id)
        if len(messages) >= 3:
            break
    return messages


def _buttons_from_plan(
    state: WorldState,
    compiled: CompiledAction,
    plan: dict[str, Any],
) -> list[StageAction]:
    raw_buttons = plan.get("buttons")
    if not isinstance(raw_buttons, list):
        return []

    buttons: list[StageAction] = []
    seen_labels: set[str] = set()
    context_terms = _button_context_terms(state, compiled, plan)
    for item in raw_buttons:
        if not isinstance(item, dict):
            continue
        label = _clean_text(item.get("label"), max_chars=48)
        if not label or label in seen_labels:
            continue
        try:
            action_type = ActionType(str(item.get("action_type", "")).strip())
        except ValueError:
            continue
        if action_type not in ALLOWED_ACTION_TYPES:
            continue
        target = _clean_text(item.get("target"), max_chars=40)
        button = StageAction(action_type, target=target, label=label)
        if not _button_is_grounded(button, context_terms):
            continue
        buttons.append(button)
        seen_labels.add(label)
        if len(buttons) >= 5:
            break
    if not any(button.action_type is ActionType.INTERRUPT for button in buttons):
        buttons.append(StageAction(ActionType.INTERRUPT, label="Wait"))
    return buttons[:5]


def _proposal_buttons_from_plan(
    state: WorldState,
    compiled: CompiledAction,
    plan: dict[str, Any],
) -> list[StageAction]:
    raw_proposals = plan.get("proposals")
    if not isinstance(raw_proposals, list):
        return []

    valid_role_ids = {
        role.role_id
        for role in state.world_pack.roles
        if role.public
    }
    buttons: list[StageAction] = []
    proposal_options: dict[str, dict[str, str]] = {}
    context_terms = _button_context_terms(state, compiled, plan)
    sorted_proposals = sorted(
        raw_proposals,
        key=lambda item: _proposal_sort_key(item) if isinstance(item, dict) else 99,
    )
    for item in sorted_proposals:
        if not isinstance(item, dict):
            continue
        role_id = _clean_text(item.get("role_id"), max_chars=40).casefold()
        if role_id not in valid_role_ids:
            continue
        stance = _clean_text(item.get("stance"), max_chars=30).casefold()
        if stance not in ALLOWED_PROPOSAL_STANCES:
            continue
        summary = _clean_text(item.get("summary"), max_chars=180)
        label = _clean_text(item.get("label"), max_chars=48)
        if not label:
            role = state.world_pack.role_by_id(role_id)
            name = role.display_name if role is not None else role_id
            label = f"Choose {name}'s plan"
        target = f"{role_id}_{stance}"
        button = StageAction(ActionType.CHOOSE_PROPOSAL, target=target, label=label)
        if not _button_is_grounded(button, context_terms, extra_text=summary):
            continue
        proposal_options[target] = {
            "role_id": role_id,
            "stance": stance,
            "label": label,
            "summary": summary,
        }
        buttons.append(button)
        if len(buttons) >= 4:
            break
    if proposal_options:
        state.flags["proposal_options"] = proposal_options
    return buttons


def _dedupe_buttons(buttons: list[StageAction]) -> list[StageAction]:
    deduped: list[StageAction] = []
    seen_labels: set[str] = set()
    seen_actions: set[str] = set()
    for button in buttons:
        if button.label in seen_labels or button.semantic_key in seen_actions:
            continue
        deduped.append(button)
        seen_labels.add(button.label)
        seen_actions.add(button.semantic_key)
        if len(deduped) >= 5:
            break
    if not any(button.action_type is ActionType.INTERRUPT for button in deduped):
        if len(deduped) >= 5:
            deduped = deduped[:4]
        deduped.append(StageAction(ActionType.INTERRUPT, label="Wait"))
    return deduped[:5]


def _supplement_buttons(state: WorldState, buttons: list[StageAction]) -> list[StageAction]:
    wait_buttons = [button for button in buttons if button.action_type is ActionType.INTERRUPT]
    supplemented = [button for button in buttons if button.action_type is not ActionType.INTERRUPT]
    latest_clue = state.clues[-1] if state.clues else "the nearest clue"
    scholar = state.world_pack.role_by_id("scholar")
    scholar_name = scholar.display_name if scholar is not None else "the scholar"
    scout = state.world_pack.role_by_id("scout")
    scout_name = scout.display_name if scout is not None else "the scout"
    location_target = _target_slug(state.world_pack.location) or "next_location"
    if state.flags.get("language") == "zh":
        fallback_actions = [
            StageAction(
                ActionType.OBSERVE_CLUE,
                target=_target_slug(latest_clue) or "clue",
                label=f"检查{latest_clue}",
            ),
            StageAction(
                ActionType.ASK_ACTOR,
                target="scholar",
                label=f"问{scholar_name}关于{latest_clue}",
            ),
            StageAction(
                ActionType.ASSIST_ACTOR,
                target="scout",
                label=f"让{scout_name}先探路",
            ),
            StageAction(
                ActionType.MOVE_LOCATION,
                target=location_target,
                label=f"穿过{state.world_pack.location}",
            ),
        ]
        wait_label = "等待"
    else:
        fallback_actions = [
            StageAction(
                ActionType.OBSERVE_CLUE,
                target=_target_slug(latest_clue) or "clue",
                label=f"Inspect {latest_clue}",
            ),
            StageAction(
                ActionType.ASK_ACTOR,
                target="scholar",
                label=f"Ask {scholar_name} about {latest_clue}",
            ),
            StageAction(
                ActionType.ASSIST_ACTOR,
                target="scout",
                label=f"Send {scout_name} ahead",
            ),
            StageAction(
                ActionType.MOVE_LOCATION,
                target=location_target,
                label=f"Move through {state.world_pack.location}",
            ),
        ]
        wait_label = "Wait"
    for action in fallback_actions:
        existing_actions = {
            button.semantic_key
            for button in supplemented
            if button.action_type is not ActionType.INTERRUPT
        }
        if action.semantic_key in existing_actions:
            continue
        action_count = len(existing_actions)
        if action_count >= 4:
            break
        supplemented.append(action)
    supplemented.append(wait_buttons[0] if wait_buttons else StageAction(ActionType.INTERRUPT, label=wait_label))
    return supplemented


def _target_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug[:40]


def _narration_from_plan(state: WorldState, plan: dict[str, Any]) -> list[str]:
    narrations: list[str] = []
    narration = _clean_text(plan.get("narration"), max_chars=700)
    if narration and not _has_forbidden_visible_text(narration):
        narrations.append(narration)

    raw_event = plan.get("dramatic_event")
    if isinstance(raw_event, dict):
        text = _clean_text(raw_event.get("text"), max_chars=700)
        event_type = _clean_text(raw_event.get("type"), max_chars=40)
        intensity = _clean_int(raw_event.get("intensity"), minimum=0, maximum=5)
        if text and intensity >= 2 and not _has_forbidden_visible_text(text):
            narrations.append(text)
            state.record_event(
                "dramatic_event",
                text,
                event_type=event_type,
                intensity=intensity,
                impact=_clean_text(raw_event.get("impact"), max_chars=160),
            )
    return _dedupe_texts(narrations)[:2]


def _system_prompt(state: WorldState, compiled: CompiledAction | None = None) -> str:
    roles = _role_prompt_cards(state, compiled)
    allowed_actions = sorted(action.value for action in ALLOWED_ACTION_TYPES)
    return (
        "You are the hidden Director for a Telegram-native multi-bot expedition stage. "
        "You do not speak as a visible character. Create the next short turn only.\n"
        "Hard rules:\n"
        "- Return JSON only.\n"
        "- Schedule at most 1-3 speaker_messages.\n"
        "- Each speaker role_id must be one of the provided public roles.\n"
        "- Each character message must be brief, vivid, and in-character.\n"
        "- Use narration for scene, environment, weather, geography, sudden turns, and consequences. "
        "Do not make actor bots explain the whole environment.\n"
        "- If the scene feels flat, add one concrete dramatic event with visible consequences: sudden weather, "
        "a ground collapse, a strange creature behavior, a portal-like relocation, or an environmental surprise. "
        "It must connect to an existing clue, anomaly, or user action.\n"
        "- Every character message must causally follow from the user's latest action, the current scene, "
        "a known clue, or the immediately previous speaker. No isolated opinions.\n"
        "- Character messages must not mention prompts, hidden policy, safety policy, backend actions, "
        "schemas, role instructions, or system rules.\n"
        "- Do not use formulaic permission language such as 'yes, but', 'okay, but', 'accepted with one "
        "condition', or 'we go three steps and stop'. Let the action begin, then let concrete world "
        "consequences, scarce tools, weather, terrain, social reactions, or magical rules create friction.\n"
        "- The default tone is adventurous curiosity. Do not let the careful voice dominate unless the user "
        "asked for a real-world dangerous method.\n"
        "- Do not make the whole team reject wild ideas. For imaginative pivots, stage structured disagreement: "
        "one bold character should try to make the idea playable, one cautious or scholarly character should "
        "state the constraint, and one character may synthesize a concrete compromise.\n"
        "- If you include proposals, include at least one bold or weird route whenever the latest action is not "
        "a real-world dangerous method. Put the adventurous route first.\n"
        "- Prefer yes_and momentum. Use explicit refusal only for unsafe real-world methods, then preserve "
        "the fantasy goal through a vivid in-world substitute.\n"
        "- Buttons must use only allowed action_type values.\n"
        "- Button labels must be fluent imperative actions, not fragments. Use a verb plus a concrete "
        "context anchor from the current scene, latest event, known clues, selected proposal, or public role. "
        "Good: 'Inspect the soybean ring', 'Ask Mori about scale dust'. Bad: 'Strange route', "
        "'Bold plan', or an unrelated new place.\n"
        "- When characters disagree, include a proposals array so the user can choose a route. "
        "Each proposal must name a public role_id, use stance bold/safe/rule/synthesis/weird, "
        "and provide a fluent button label grounded in that speaker's just-stated route.\n"
        "- Always include an interrupt/wait-style button.\n"
        "- Do not provide real dangerous instructions.\n"
        "- Do not claim to create real files, call real plugins, send emails, or upload anything.\n"
        "- Respect user pivots; do not force the old route if the objective changed.\n"
        "- Do not schedule the log/recorder role unless the user explicitly asks for a summary, record, report, "
        "outline, or recap. Use narration for discoveries instead.\n"
        "JSON schema:\n"
        "{"
        '"narration": string, '
        '"dramatic_event": {"type": string, "intensity": number, "text": string, "impact": string}, '
        '"scene_update": string, '
        '"objective_update": string, '
        '"clues_added": [string], '
        '"risk_delta": number, '
        '"facts_referenced": [string], '
        '"new_knowledge": [{"text": string, "source": "observed|deduced|remembered|user|world_rule", "because": [string]}], '
        '"location_update": string, '
        '"speaker_messages": [{"role_id": string, "intent": string, "text": string}], '
        '"proposals": [{"role_id": string, "stance": string, "label": string, "summary": string}], '
        '"buttons": [{"label": string, "action_type": string, "target": string}]'
        "}\n"
        f"Public roles: {json.dumps(roles, ensure_ascii=False)}\n"
        f"Allowed action_type values: {json.dumps(allowed_actions)}"
    )


def _user_prompt(state: WorldState, compiled: CompiledAction) -> str:
    active = state.active_objective.title if state.active_objective else ""
    recent_history = state.history[-8:]
    world = state.world_pack
    payload = {
        "world": {
            "name": world.name,
            "type": world.world_type,
            "tone": world.tone,
            "rules": world.rules,
            "ecology": world.ecology,
            "anomalies": world.anomalies,
        },
        "state": {
            "scene": state.scene,
            "active_objective": active,
            "clues": state.clues,
            "turn_number": state.turn_number,
            "recent_history": recent_history,
            "knowledge": knowledge_snapshot(state),
        },
        "turn_contract": {
            "causal_focus": _causal_focus(state, compiled),
            "knowledge_rules": (
                "If you introduce a new object, creature, location property, or world rule, put it in "
                "new_knowledge with a source and because list. Deduced/remembered/world_rule entries "
                "must cite existing facts, clues, scene details, or the user's current action."
            ),
            "narration_policy": (
                "Use narration for environment, scene pressure, major turns, and new discoveries. "
                "Actor messages should react to events rather than recite summaries."
            ),
            "visible_style": (
                "Every spoken line should connect to the user's action, a clue, or the previous speaker. "
                "Do not reveal planner language, task settings, backend actions, or safety policy. "
                "Avoid AI-like permission formulas such as yes-but, okay-but, one-condition, "
                "or three-steps-then-stop. Show constraints as events or tradeoffs inside the scene."
            ),
            "decision_bias": (
                "Prefer playable forward motion. If caution matters, express it as a concrete "
                "cost, preparation, omen, terrain problem, or tool limitation after the action starts."
            ),
            "button_rules": (
                "Every non-wait button must be an executable next action and must reuse a concrete noun, "
                "role name, clue, location, or event from the visible turn/state. Do not create unrelated "
                "destinations, creatures, tools, or vague labels just to make a button short."
            ),
        },
        "compiled_user_action": {
            "raw_text": compiled.raw_text,
            "category": compiled.category.value,
            "strategy": compiled.strategy.value,
            "semantic_action": compiled.action.semantic_key,
            "goal": compiled.goal,
            "method": compiled.method,
            "objects": compiled.objects,
            "addressed_role": compiled.addressed_role,
            "safety_note": compiled.safety_note,
            "selected_proposal": _selected_proposal(state, compiled),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _selected_proposal(state: WorldState, compiled: CompiledAction) -> dict[str, str]:
    if compiled.action.action_type is not ActionType.CHOOSE_PROPOSAL:
        return {}
    options = state.flags.get("proposal_options")
    if not isinstance(options, dict):
        return {"target": compiled.action.target}
    selected = options.get(compiled.action.target)
    if not isinstance(selected, dict):
        return {"target": compiled.action.target}
    return {
        "target": compiled.action.target,
        "role_id": str(selected.get("role_id", "")),
        "stance": str(selected.get("stance", "")),
        "label": str(selected.get("label", "")),
        "summary": str(selected.get("summary", "")),
    }


def _role_prompt_cards(state: WorldState, compiled: CompiledAction | None = None) -> list[dict[str, str]]:
    public_styles = {
        "mentor": "careful expedition leader; turns risk into practical preparations",
        "scholar": "curious rule-finder; explains how strange effects could work",
        "scout": "bold pathfinder; proposes fast tests and forward movement",
        "log": "recorder-synthesizer; turns debate into a concrete next step",
        "guide": "local improviser; makes odd ideas playable through local routes",
    }
    cards: list[dict[str, str]] = []
    for role in state.world_pack.roles:
        if not role.public:
            continue
        if role.role_id == "log" and not _log_allowed(compiled):
            continue
        cards.append(
            {
                "role_id": role.role_id,
                "name": role.display_name,
                "archetype": role.archetype,
                "personality": role.personality,
                "public_style": public_styles.get(role.role_id, "expedition teammate"),
            }
        )
    return cards


def _causal_focus(state: WorldState, compiled: CompiledAction) -> str:
    selected = _selected_proposal(state, compiled)
    if selected:
        summary = selected.get("summary") or selected.get("label") or selected.get("target", "")
        return f"The user chose a route: {summary}. Show the immediate consequence of that choice."
    clue = state.clues[-1] if state.clues else "the current scene"
    return (
        f"The user action is {compiled.raw_text!r}. Connect the next beat to {clue!r} "
        f"and the current objective {state.active_objective.title if state.active_objective else ''!r}."
    )


def _proposal_sort_key(item: dict[str, Any]) -> int:
    stance = _clean_text(item.get("stance"), max_chars=30).casefold()
    return PROPOSAL_STANCE_ORDER.get(stance, 99)


def _button_context_terms(
    state: WorldState,
    compiled: CompiledAction,
    plan: dict[str, Any],
) -> set[str]:
    chunks: list[str] = [
        state.scene,
        compiled.raw_text,
        compiled.goal,
        compiled.method,
        compiled.action.target,
        state.world_pack.location,
        state.world_pack.name,
    ]
    if state.active_objective is not None:
        chunks.append(state.active_objective.title)
        chunks.extend(state.active_objective.notes[-3:])
    chunks.extend(state.clues[-8:])
    chunks.extend(state.world_pack.ecology)
    chunks.extend(state.world_pack.anomalies)
    chunks.extend(state.world_pack.rules)
    chunks.extend(_clean_list(plan.get("clues_added"), max_items=5, max_chars=80))
    chunks.append(_clean_text(plan.get("scene_update"), max_chars=700))
    chunks.append(_clean_text(plan.get("objective_update"), max_chars=220))
    chunks.append(_clean_text(plan.get("narration"), max_chars=700))
    raw_event = plan.get("dramatic_event")
    if isinstance(raw_event, dict):
        chunks.append(_clean_text(raw_event.get("text"), max_chars=700))
        chunks.append(_clean_text(raw_event.get("impact"), max_chars=160))
    for item in plan.get("speaker_messages", []):
        if isinstance(item, dict):
            chunks.append(_clean_text(item.get("text"), max_chars=260))
    for role in state.world_pack.roles:
        chunks.extend([role.role_id, role.display_name, role.archetype])

    terms: set[str] = set()
    for chunk in chunks:
        terms.update(_meaningful_terms(chunk))
    return terms


def _button_is_grounded(
    button: StageAction,
    context_terms: set[str],
    *,
    extra_text: str = "",
) -> bool:
    if button.action_type is ActionType.INTERRUPT:
        return _label_has_any(button.label, "wait", "pause", "stop", "hold", "等等", "等待", "暂停")
    if _has_forbidden_visible_text(button.label):
        return False
    label_terms = _meaningful_terms(f"{button.label} {button.target} {extra_text}")
    if not label_terms:
        return False
    if _looks_fragmentary_button(button.label):
        return False
    if not _has_action_language(button):
        return False
    if button.action_type is ActionType.RESUME_OBJECTIVE:
        return _label_has_any(button.label, "resume", "return", "restore", "继续", "回到", "恢复")
    return bool(label_terms & context_terms)


def _looks_fragmentary_button(label: str) -> bool:
    normalized = label.strip()
    if len(normalized) < 4:
        return True
    if normalized.endswith((",", "，", ":", "：", "-", "/")):
        return True
    words = normalized.split()
    if len(words) == 1 and not _contains_cjk(normalized):
        return True
    vague_labels = {
        "mystery",
        "strange clue",
        "new route",
        "next step",
        "the plan",
        "bold plan",
        "safe plan",
        "weird plan",
        "神秘线索",
        "新路线",
        "下一步",
        "大胆方案",
        "安全方案",
    }
    return normalized.casefold() in vague_labels


def _has_action_language(button: StageAction) -> bool:
    label = button.label.casefold()
    action_words = {
        ActionType.OBSERVE_CLUE: (
            "inspect",
            "check",
            "observe",
            "compare",
            "test",
            "examine",
            "检查",
            "观察",
            "比较",
            "测试",
        ),
        ActionType.ASK_ACTOR: ("ask", "consult", "question", "询问", "问", "请教"),
        ActionType.ASSIST_ACTOR: ("send", "help", "assist", "support", "follow", "让", "协助", "支援", "跟随"),
        ActionType.MOVE_LOCATION: ("go", "move", "enter", "follow", "cross", "climb", "前往", "进入", "移动", "跟随"),
        ActionType.COLLECT_EVIDENCE: ("collect", "sample", "gather", "mark", "记录", "采集", "收集", "标记"),
        ActionType.GENERATE_REPORT_OUTLINE: ("draft", "outline", "report", "分析", "整理", "报告", "大纲"),
        ActionType.GENERATE_SUMMARY: ("summarize", "recap", "总结", "复盘"),
        ActionType.CHOOSE_PROPOSAL: (
            "choose",
            "use",
            "take",
            "try",
            "follow",
            "let",
            "adopt",
            "选择",
            "采用",
            "尝试",
            "跟随",
            "让",
        ),
    }
    allowed = action_words.get(button.action_type, ())
    return any(word in label for word in allowed)


def _meaningful_terms(text: str) -> set[str]:
    normalized = text.casefold()
    terms = {
        word
        for word in re.findall(r"[a-z0-9_]+", normalized)
        if _is_meaningful_word(word)
    }
    terms.update(
        token
        for token in _cjk_tokens(normalized)
        if len(token) >= 2
    )
    return terms


def _is_meaningful_word(word: str) -> bool:
    if len(word) < 3:
        return False
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "into",
        "from",
        "that",
        "this",
        "then",
        "before",
        "after",
        "route",
        "plan",
        "step",
        "thing",
        "something",
        "current",
        "choose",
        "use",
        "take",
        "try",
        "ask",
        "go",
        "move",
        "inspect",
        "check",
        "observe",
        "follow",
    }
    return word not in stopwords


def _cjk_tokens(text: str) -> set[str]:
    chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    if not chars:
        return set()
    joined = "".join(chars)
    return {joined[index : index + 2] for index in range(max(0, len(joined) - 1))}


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _label_has_any(label: str, *needles: str) -> bool:
    normalized = label.casefold()
    return any(needle.casefold() in normalized for needle in needles)


def _log_allowed(compiled: CompiledAction | None) -> bool:
    if compiled is None:
        return False
    if compiled.action.action_type is ActionType.GENERATE_SUMMARY:
        return True
    haystack = " ".join(
        [
            compiled.raw_text,
            compiled.goal,
            compiled.method,
            compiled.action.label,
            compiled.action.target,
        ]
    ).casefold()
    summary_terms = (
        "summary",
        "summarize",
        "recap",
        "总结",
        "概括",
        "复盘",
    )
    return any(term in haystack for term in summary_terms)


def _dedupe_texts(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        deduped.append(value)
        seen.add(key)
    return deduped


def _has_forbidden_visible_text(text: str) -> bool:
    normalized = text.casefold()
    return any(term.casefold() in normalized for term in FORBIDDEN_VISIBLE_TEXT)


def _has_formulaic_constraint_text(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    formulaic_terms = (
        "yes, but",
        "okay, but",
        "ok, but",
        "sure, but",
        "accepted with one condition",
        "with one condition",
        "one step at a time",
        "three steps",
        "and stop",
        "we can, but",
        "we can do this, but",
        "好的，但",
        "可以，但",
        "能，但",
        "接受，但",
        "有一个条件",
        "走三步",
        "就停",
    )
    return any(term in normalized for term in formulaic_terms)


def _role_already_speaks(messages: list[StageMessage], role_id: str) -> bool:
    return any(message.speaker_role_id == role_id for message in messages)


def _clean_text(value: Any, *, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.strip().split())
    return cleaned[:max_chars]


def _clean_list(value: Any, *, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        cleaned = _clean_text(item, max_chars=max_chars)
        if cleaned:
            items.append(cleaned)
        if len(items) >= max_items:
            break
    return items


def _clean_int(value: Any, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(minimum, min(maximum, value))
    if isinstance(value, float):
        return max(minimum, min(maximum, int(value)))
    return 0
