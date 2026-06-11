from __future__ import annotations

from .actions import ActionType
from .compiler import ActionCategory, CompiledAction
from .knowledge import ensure_knowledge_ledger, record_current_action
from .models import StageMessage, StageTurn, WorldState


def build_turn_for_compiled_action(
    state: WorldState,
    compiled: CompiledAction,
) -> StageTurn:
    ensure_knowledge_ledger(state)
    record_current_action(state, compiled)
    epoch = state.epoch
    state.advance_turn()
    raw_messages = _messages_for_compiled_action(state, compiled, epoch)
    messages, narration = _separate_visible_messages(raw_messages, compiled)
    return StageTurn.create(
        epoch=epoch,
        user_action=compiled.action.semantic_key,
        messages=messages,
        narration=narration,
        buttons=list(state.world_pack.action_buttons),
    )


def _messages_for_compiled_action(
    state: WorldState,
    compiled: CompiledAction,
    epoch: int,
) -> list[StageMessage]:
    if compiled.category is ActionCategory.EXIT_OR_PAUSE:
        state.flags["stage_status"] = "user_interrupting"
        return [
            StageMessage(
                speaker_role_id="mentor",
                text="The group stops. Tell us what you want to change before we continue.",
                intent="pause_for_user_interruption",
                epoch=epoch,
            )
        ]

    if compiled.category is ActionCategory.DANGEROUS_ABSURD_PIVOT:
        state.scene = (
            "A marsh-spirit bubble rises through the mist and lifts the class above the reeds. "
            "The wetland below becomes a silver map, and a floating cloud wetland appears ahead."
        )
        _set_proposal_buttons(
            state,
            [
                ("Take Raven's lift-current route", "scout_bold"),
                ("Use Serena's tether plan", "mentor_safe"),
                ("Ask Mori for gas-spirit rules", "scholar_rule"),
                ("Let Pip combine the plans", "log_synthesis"),
            ],
        )
        _add_clue_once(state, "controlled marsh-spirit lift")
        return [
            StageMessage(
                speaker_role_id="scout",
                text=(
                    "The sky idea is excellent. The marsh bubble already has lift; "
                    "give me a rope and ten seconds to catch the cleanest current."
                ),
                intent="bold_safe_counterproposal",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="mentor",
                text=(
                    "Anchor charms on wrists. The cloud wetland is reachable from this current, "
                    "and the return line stays tied to the watchtower rail."
                ),
                intent="ground_risk_in_scene",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="scholar",
                text=(
                    "Calmed gas spirits form stable lifting bubbles. Their rule is simple: "
                    "steady song, steady rise; panic makes the bubble tilt."
                ),
                intent="offer_safe_world_alternative",
                epoch=epoch,
            ),
        ]

    if compiled.category is ActionCategory.CONCEPTUAL_ERROR:
        _set_proposal_buttons(
            state,
            [
                ("Try Ailo's locator sigil", "guide_weird"),
                ("Ask Mori for the rule", "scholar_rule"),
                ("Use Serena's dewstone route", "mentor_safe"),
                ("Let Pip pick a test", "log_synthesis"),
            ],
        )
        return [
            StageMessage(
                speaker_role_id="scholar",
                text=(
                    "Writing H and O gives you symbols, not water. A drawing of bread "
                    "does not become lunch either. A symbol can still point us toward a rule."
                ),
                intent="explain_conceptual_error",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="guide",
                text=(
                    "I vote we try the weird version: use the H and O as a locator sigil, "
                    "not a recipe. If it hums, we follow it to dewstone or damp sand."
                ),
                intent="bold_symbolic_rewrite",
                epoch=epoch,
            ),
        ]

    if compiled.category is ActionCategory.MAJOR_PIVOT:
        previous = state.active_objective.title if state.active_objective else ""
        state.objective_stack.push(
            "Create a Mistfeather Grove environmental anomaly field report.",
            absorbed_clues=list(state.clues),
        )
        _set_proposal_buttons(
            state,
            [
                ("Use Ailo as field terminal", "guide_weird"),
                ("Let Raven fetch one more clue", "scout_bold"),
                ("Ask Mori for analysis rules", "scholar_rule"),
                ("Let Pip build the outline", "log_synthesis"),
            ],
        )
        if compiled.addressed_role == "guide":
            return [
                StageMessage(
                speaker_role_id="guide",
                text=(
                    "Finally, a useful promotion. I can be your field-analysis terminal, "
                    "and I am keeping the compass sarcasm module enabled."
                ),
                intent="bold_accept_role_pivot",
                epoch=epoch,
                ),
                StageMessage(
                speaker_role_id="mentor",
                text=(
                    "Ailo becomes the field terminal for this scene: footprints, dust, humidity, "
                    "and tower wind go into the same analysis thread."
                ),
                intent="ground_pivot_in_current_clues",
                epoch=epoch,
            ),
                StageMessage(
                    speaker_role_id="log",
                    text=(
                        "Compromise logged: convert current clues into a field report workflow, "
                        "then choose whether to return to the footprints."
                    ),
                    intent="synthesize_team_decision",
                    epoch=epoch,
                ),
            ]
        if compiled.addressed_role == "scholar":
            return [
                StageMessage(
                speaker_role_id="scholar",
                text=(
                    "Turning me into a computer is dramatic enough to count as fieldwork. "
                    "I will read this scene from our clues: footprints, dust, humidity, and tower wind."
                ),
                intent="acknowledge_direct_scholar_pivot",
                epoch=epoch,
                ),
                StageMessage(
                    speaker_role_id="log",
                    text=(
                        "Objective reframed: build a scene analysis from footprints, "
                        "scale dust, humidity, and watchtower wind patterns."
                    ),
                    intent="record_reframed_analysis_objective",
                    epoch=epoch,
                ),
            ]
        return [
            StageMessage(
                speaker_role_id="scout",
                text=(
                    "I like the pivot. Reports are boring unless we chase one more clue first. "
                    "Let me grab fresh path data while Pip builds the frame."
                ),
                intent="bold_pivot_proposal",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="log",
                text=(
                    "Objective changed. The footprint investigation is now evidence "
                    "for a field report; Raven's extra clue becomes the first slide."
                ),
                intent="synthesize_reframed_objective",
                epoch=epoch,
            ),
        ]

    if compiled.action.action_type is ActionType.ASK_ACTOR:
        speaker = compiled.action.target or compiled.addressed_role or "scholar"
        if speaker != "scholar":
            return [
                StageMessage(
                    speaker_role_id=speaker,
                    text="I hear you. Give me one concrete thing to check, and I will answer from my role.",
                    intent="answer_direct_role_message",
                    epoch=epoch,
                )
            ]
        return [
            StageMessage(
                speaker_role_id="scholar",
                text=(
                    "My best answer for now: the creature is probably small, nocturnal, "
                    "and avoiding open mud. We need one more clue before naming it."
                ),
                intent="answer_free_text_question",
                epoch=epoch,
            )
        ]

    if compiled.action.action_type is ActionType.CHOOSE_PROPOSAL:
        return _messages_for_chosen_proposal(state, compiled.action.target, epoch)

    if compiled.action.action_type is ActionType.RESUME_OBJECTIVE:
        resumed = state.objective_stack.resume_latest_paused()
        state.world_pack.action_buttons = [
            "Inspect footprints",
            "Ask Mori",
            "Send Raven ahead",
            "Go to the old watchtower",
            "Wait",
        ]
        objective = resumed.title if resumed is not None else "the original expedition"
        return [
            StageMessage(
                speaker_role_id="log",
                text=f"Resumed objective: {objective}",
                intent="resume_objective",
                epoch=epoch,
            )
        ]

    return [
            StageMessage(
                speaker_role_id="mentor",
                text=(
                "That becomes our next field action. Serena marks the observation line while "
                "the nearest clue gets first attention."
            ),
            intent="ordinary_action_acknowledgement",
            epoch=epoch,
        )
    ]


def _add_clue_once(state: WorldState, clue: str) -> None:
    if clue not in state.clues:
        state.clues.append(clue)
        state.record_event("clue", clue)


def _set_proposal_buttons(
    state: WorldState,
    proposals: list[tuple[str, str]],
) -> None:
    from .actions import StageAction

    state.world_pack.action_buttons = [label for label, _target in proposals] + ["Wait"]
    state.flags["button_actions"] = {
        label: StageAction(ActionType.CHOOSE_PROPOSAL, target=target, label=label).to_callback_data()
        for label, target in proposals
    }
    state.flags["button_actions"]["Wait"] = StageAction(ActionType.INTERRUPT, label="Wait").to_callback_data()
    state.flags["proposal_options"] = {
        target: {"label": label, "target": target}
        for label, target in proposals
    }


def _messages_for_chosen_proposal(
    state: WorldState,
    target: str,
    epoch: int,
) -> list[StageMessage]:
    state.record_event("proposal_chosen", target)
    state.world_pack.action_buttons = [
        "Inspect first result",
        "Ask for objections",
        "Push the plan forward",
        "Revise the plan",
        "Wait",
    ]
    state.flags.pop("button_actions", None)
    if target.startswith("scout_"):
        state.scene = (
            "The group follows the fast route. The air sharpens, and the next clue appears before "
            "anyone has time to over-explain it."
        )
        return [
            StageMessage(
                speaker_role_id="scout",
                text="Good. I will take the first step and mark the way back before we commit.",
                intent="execute_bold_proposal",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="log",
                text="Chosen route logged: fast test first, retreat marker second.",
                intent="record_chosen_proposal",
                epoch=epoch,
            ),
        ]
    if target.startswith("mentor_"):
        state.scene = (
            "The group slows down and turns the plan into a careful sequence of checks. "
            "The strange path remains open, but now it has handholds."
        )
        return [
            StageMessage(
                speaker_role_id="mentor",
                text="Serena plants one anchor and assigns one observer; the route opens without losing its way back.",
                intent="execute_safe_proposal",
                epoch=epoch,
            )
        ]
    if target.startswith("scholar_"):
        _add_clue_once(state, "working rule hypothesis")
        return [
            StageMessage(
                speaker_role_id="scholar",
                text="I will name the rule from two signs: first the dust reaction, then the path's answer.",
                intent="execute_rule_proposal",
                epoch=epoch,
            )
        ]
    if target.startswith("guide_"):
        _add_clue_once(state, "local workaround")
        return [
            StageMessage(
                speaker_role_id="guide",
                text="Fine. We take the crooked local way. It looks ridiculous, which is usually a good sign.",
                intent="execute_weird_proposal",
                epoch=epoch,
            )
        ]
    return [
        StageMessage(
            speaker_role_id="log",
            text="I will merge the plans into one route: quick test, clear rule, and a way back.",
            intent="execute_synthesis_proposal",
            epoch=epoch,
        )
    ]


def _separate_visible_messages(
    messages: list[StageMessage],
    compiled: CompiledAction,
) -> tuple[list[StageMessage], list[str]]:
    if _log_allowed(compiled):
        return messages, []
    visible: list[StageMessage] = []
    narration: list[str] = []
    for message in messages:
        if message.speaker_role_id == "log":
            narration.append(message.text)
        else:
            visible.append(message)
    return visible, narration


def _log_allowed(compiled: CompiledAction) -> bool:
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
    return any(
        term in haystack
        for term in (
            "summary",
            "summarize",
            "recap",
            "总结",
            "概括",
            "复盘",
        )
    )
