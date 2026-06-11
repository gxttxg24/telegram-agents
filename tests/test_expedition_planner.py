from __future__ import annotations

import asyncio
from typing import Any

from tg_agent_bot.expedition.actions import ActionType, StageAction
from tg_agent_bot.expedition.compiler import compiled_from_stage_action
from tg_agent_bot.expedition.models import ObjectiveStatus
from tg_agent_bot.expedition.planner import build_directed_turn
from tg_agent_bot.expedition.stage import action_keyboard
from tg_agent_bot.expedition.templates import create_world_state


class FakeLLM:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    async def json_reply(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_llm_planner_updates_scene_messages_and_dynamic_buttons() -> None:
    state = create_world_state("magic_academy")
    action = StageAction(ActionType.OBSERVE_CLUE, target="footprints")
    llm = FakeLLM(
        {
            "scene_update": "Mori kneels beside the glowing prints as mist beads on the reeds.",
            "objective_update": "Identify what left the prints before approaching the tower.",
            "clues_added": ["triangular toe pattern", "cold blue scale dust"],
            "speaker_messages": [
                {
                    "role_id": "scholar",
                    "intent": "explain_clue",
                    "text": "The toe pattern is triangular. That narrows it to a light marsh reptile.",
                },
                {
                    "role_id": "scout",
                    "intent": "watch_path",
                    "text": "The tower path is quiet, but the reeds are bent on only one side.",
                },
                {
                    "role_id": "mentor",
                    "intent": "cautious_boundary",
                    "text": "We can test it, but nobody touches the dust directly.",
                },
            ],
            "proposals": [
                {
                    "role_id": "scout",
                    "stance": "bold",
                    "label": "Follow Raven's reed route",
                    "summary": "Move fast along the bent reeds.",
                },
                {
                    "role_id": "mentor",
                    "stance": "safe",
                    "label": "Use Serena's slow check",
                    "summary": "Anchor the group before moving.",
                },
            ],
            "buttons": [
                {
                    "label": "Compare toe pattern",
                    "action_type": "observe_clue",
                    "target": "toe_pattern",
                },
                {
                    "label": "Ask Mori about scale dust",
                    "action_type": "ask_actor",
                    "target": "scholar",
                },
                {
                    "label": "Wait",
                    "action_type": "interrupt",
                    "target": "",
                },
            ],
        }
    )

    result = asyncio.run(build_directed_turn(llm, state, compiled_from_stage_action(action)))

    assert result.used_llm
    assert state.scene.startswith("Mori kneels")
    assert state.flags["risk_score"] == 0
    assert "triangular toe pattern" in state.clues
    assert [message.speaker_role_id for message in result.turn.queue.messages] == [
        "scholar",
        "scout",
        "mentor",
    ]
    assert state.world_pack.action_buttons == [
        "Follow Raven's reed route",
        "Use Serena's slow check",
        "Compare toe pattern",
        "Ask Mori about scale dust",
        "Wait",
    ]
    keyboard = action_keyboard(state)
    assert keyboard.inline_keyboard[0][0].callback_data == (
        "expedition:action:choose_proposal:scout_bold"
    )
    assert keyboard.inline_keyboard[0][1].callback_data == (
        "expedition:action:choose_proposal:mentor_safe"
    )
    assert state.flags["proposal_options"]["scout_bold"]["summary"] == (
        "Move fast along the bent reeds."
    )
    assert any(event["kind"] == "scene_update" for event in state.history)
    assert any(event["kind"] == "objective_update" for event in state.history)
    assert "structured disagreement" in llm.calls[0]["system"]
    assert '"proposals"' in llm.calls[0]["system"]
    assert "boundaries" not in llm.calls[0]["system"]
    assert "cautious voice" not in llm.calls[0]["system"]
    assert "causal_focus" in llm.calls[0]["user"]


def test_llm_planner_applies_bounded_risk_delta() -> None:
    state = create_world_state("magic_academy")
    state.flags["risk_score"] = 4
    llm = FakeLLM(
        {
            "scene_update": "The watchtower bell rings under the marsh water.",
            "risk_delta": 99,
            "speaker_messages": [
                {
                    "role_id": "mentor",
                    "intent": "raise_caution",
                    "text": "That bell means we slow down and test the path first.",
                }
            ],
            "buttons": [{"label": "Wait", "action_type": "interrupt", "target": ""}],
        }
    )

    asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.MOVE_LOCATION, target="tower")),
        )
    )

    assert state.flags["risk_score"] == 5
    assert any(event["kind"] == "risk_delta" and event["text"] == "2" for event in state.history)


def test_llm_planner_resume_action_restores_paused_objective() -> None:
    state = create_world_state("magic_academy")
    original = state.active_objective
    state.objective_stack.push("Create a field report.", absorbed_clues=list(state.clues))
    llm = FakeLLM(
        {
            "scene_update": "The class returns attention to the blue footprints.",
            "speaker_messages": [
                {
                    "role_id": "log",
                    "intent": "resume_objective",
                    "text": "Original footprint investigation is active again.",
                }
            ],
            "buttons": [{"label": "Wait", "action_type": "interrupt", "target": ""}],
        }
    )

    asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.RESUME_OBJECTIVE)),
        )
    )

    assert original.status is ObjectiveStatus.ACTIVE
    assert state.active_objective is original


def test_llm_planner_allows_log_when_user_asks_for_summary() -> None:
    state = create_world_state("magic_academy")
    result = asyncio.run(
        build_directed_turn(
            FakeLLM(
                {
                    "speaker_messages": [
                        {
                            "role_id": "log",
                            "intent": "resume_objective",
                            "text": "Original footprint investigation is active again.",
                        }
                    ],
                    "buttons": [{"label": "Wait", "action_type": "interrupt", "target": ""}],
                }
            ),
            state,
            compiled_from_stage_action(StageAction(ActionType.GENERATE_SUMMARY)),
        )
    )
    assert result.turn.queue.messages[0].speaker_role_id == "log"


def test_llm_planner_rejects_unknown_roles_and_actions() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(
        {
            "scene_update": "The mist thickens.",
            "speaker_messages": [
                {"role_id": "director", "intent": "bad", "text": "I should not speak."},
                {"role_id": "scholar", "intent": "ok", "text": "This clue is real."},
            ],
            "buttons": [
                {"label": "Run code", "action_type": "execute_code", "target": ""},
                {"label": "Wait", "action_type": "interrupt", "target": ""},
            ],
        }
    )

    result = asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.ASK_ACTOR, target="scholar")),
        )
    )

    assert [message.speaker_role_id for message in result.turn.queue.messages] == ["scholar"]
    assert state.world_pack.action_buttons[-1] == "Wait"
    assert len(state.world_pack.action_buttons) == 5
    assert "Inspect silver-blue wetland mist" in state.world_pack.action_buttons


def test_llm_planner_filters_meta_speech_and_prioritizes_adventurous_proposals() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(
        {
            "scene_update": "The reeds open toward a hidden plank path.",
            "speaker_messages": [
                {
                    "role_id": "mentor",
                    "intent": "bad_meta",
                    "text": "According to the system prompt, my safety policy says no.",
                },
                {
                    "role_id": "scout",
                    "intent": "causal_move",
                    "text": "The bent reeds point somewhere. I can test the plank path before it sinks.",
                },
            ],
            "proposals": [
                {
                    "role_id": "mentor",
                    "stance": "safe",
                    "label": "Use Serena's careful check",
                    "summary": "Test every board slowly.",
                },
                {
                    "role_id": "scout",
                    "stance": "bold",
                    "label": "Follow Raven onto the planks",
                    "summary": "Move first while the path is visible.",
                },
            ],
            "buttons": [{"label": "Wait", "action_type": "interrupt", "target": ""}],
        }
    )

    result = asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.OBSERVE_CLUE, target="reeds")),
        )
    )

    assert [message.speaker_role_id for message in result.turn.queue.messages] == ["scout"]
    assert result.turn.queue.messages[0].text.startswith("The bent reeds")
    assert state.world_pack.action_buttons[0] == "Follow Raven onto the planks"
    assert state.world_pack.action_buttons[1] == "Use Serena's careful check"


def test_llm_planner_rejects_ungrounded_or_fragmentary_buttons() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(
        {
            "scene_update": "The blue footprints circle a patch of soybeans beside the reeds.",
            "clues_added": ["soybean ring", "blue scale dust"],
            "speaker_messages": [
                {
                    "role_id": "scholar",
                    "intent": "connect_evidence",
                    "text": "The soybean ring is fresh, and the dust reacts only at its edge.",
                }
            ],
            "proposals": [
                {
                    "role_id": "scout",
                    "stance": "bold",
                    "label": "Ride the dragon to the palace",
                    "summary": "Leave the marsh for an unrelated palace dragon.",
                },
                {
                    "role_id": "mentor",
                    "stance": "safe",
                    "label": "Safe plan",
                    "summary": "A vague safe plan.",
                },
            ],
            "buttons": [
                {
                    "label": "Strange route",
                    "action_type": "move_location",
                    "target": "palace",
                },
                {
                    "label": "Inspect the soybean ring",
                    "action_type": "observe_clue",
                    "target": "soybean_ring",
                },
                {
                    "label": "Ask Mori about blue scale dust",
                    "action_type": "ask_actor",
                    "target": "scholar",
                },
                {
                    "label": "Wait",
                    "action_type": "interrupt",
                    "target": "",
                },
            ],
        }
    )

    asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.OBSERVE_CLUE, target="soybeans")),
        )
    )

    assert state.world_pack.action_buttons[0:2] == [
        "Inspect the soybean ring",
        "Ask Mori about blue scale dust",
    ]
    assert state.world_pack.action_buttons[-1] == "Wait"
    assert len(state.world_pack.action_buttons) == 5
    assert "proposal_options" not in state.flags
    assert "button_rules" in llm.calls[0]["user"]
    assert "Button labels must be fluent imperative actions" in llm.calls[0]["system"]


def test_llm_planner_filters_formulaic_yes_but_constraints() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(
        {
            "scene_update": "The reeds lean toward the old watchtower.",
            "speaker_messages": [
                {
                    "role_id": "mentor",
                    "intent": "formulaic_constraint",
                    "text": "Okay, but we go one step at a time and stop after three steps.",
                },
                {
                    "role_id": "scout",
                    "intent": "scene_forward",
                    "text": "The reed line already bends toward the tower; I can mark the dry stones as we move.",
                },
            ],
            "buttons": [
                {
                    "label": "Follow the reed line",
                    "action_type": "move_location",
                    "target": "old_watchtower",
                },
                {"label": "Wait", "action_type": "interrupt", "target": ""},
            ],
        }
    )

    result = asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.MOVE_LOCATION, target="tower")),
        )
    )

    assert [message.speaker_role_id for message in result.turn.queue.messages] == ["scout"]
    assert "yes-but" in llm.calls[0]["user"]
    assert "Do not use formulaic permission language" in llm.calls[0]["system"]


def test_llm_planner_records_supported_new_knowledge_and_announces_it() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(
        {
            "scene_update": "The blue footprints circle a patch of soybeans beside the reeds.",
            "facts_referenced": ["blue glowing footprints"],
            "new_knowledge": [
                {
                    "text": "jump mice may be nearby",
                    "source": "deduced",
                    "because": ["blue glowing footprints", "soybeans"],
                }
            ],
            "speaker_messages": [
                {
                    "role_id": "scholar",
                    "intent": "connect_evidence",
                    "text": "I have seen this in a field book: jump mice sometimes mark territory with soybeans.",
                }
            ],
            "buttons": [{"label": "Wait", "action_type": "interrupt", "target": ""}],
        }
    )

    result = asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.OBSERVE_CLUE, target="soybeans")),
        )
    )

    assert "jump mice may be nearby" in state.clues
    assert any(event["kind"] == "knowledge_added" for event in state.history)
    assert [message.speaker_role_id for message in result.turn.queue.messages] == ["scholar"]
    assert result.turn.narration[-1].startswith("New finding:")
    assert "knowledge" in llm.calls[0]["user"]
    assert "new_knowledge" in llm.calls[0]["system"]


def test_llm_planner_uses_narration_for_dramatic_events_and_filters_log() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(
        {
            "narration": "Rain needles through the grove, turning every blue footprint into a tiny lantern.",
            "dramatic_event": {
                "type": "weather_shift",
                "intensity": 4,
                "text": "A warm downburst folds the reeds flat, revealing a round hole under the old path.",
                "impact": "The team must choose whether to inspect the hole or retreat to higher ground.",
            },
            "speaker_messages": [
                {
                    "role_id": "log",
                    "intent": "record_weather",
                    "text": "Weather shift logged for the field report.",
                },
                {
                    "role_id": "scout",
                    "intent": "react_to_hole",
                    "text": "That hole was hidden by the reeds. I can mark the rim before anyone gets close.",
                },
            ],
            "buttons": [{"label": "Wait", "action_type": "interrupt", "target": ""}],
        }
    )

    result = asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.OBSERVE_CLUE, target="footprints")),
        )
    )

    assert result.turn.narration == [
        "Rain needles through the grove, turning every blue footprint into a tiny lantern.",
        "A warm downburst folds the reeds flat, revealing a round hole under the old path.",
    ]
    assert [message.speaker_role_id for message in result.turn.queue.messages] == ["scout"]
    assert any(event["kind"] == "dramatic_event" for event in state.history)
    assert "narration_policy" in llm.calls[0]["user"]
    assert "Do not schedule the log/recorder role" in llm.calls[0]["system"]


def test_llm_planner_rejects_unsupported_new_knowledge() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(
        {
            "scene_update": "The path remains quiet beside the reeds.",
            "new_knowledge": [
                {
                    "text": "a glass whale owns the tower",
                    "source": "deduced",
                    "because": ["royal whale contract"],
                }
            ],
            "speaker_messages": [
                {
                    "role_id": "scout",
                    "intent": "stay_grounded",
                    "text": "Nothing here points to a whale. I only see reeds and the old path.",
                }
            ],
            "buttons": [{"label": "Wait", "action_type": "interrupt", "target": ""}],
        }
    )

    result = asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.OBSERVE_CLUE, target="reeds")),
        )
    )

    assert "a glass whale owns the tower" not in state.clues
    assert any(event["kind"] == "knowledge_rejected" for event in state.history)
    assert [message.speaker_role_id for message in result.turn.queue.messages] == ["scout"]


def test_llm_planner_falls_back_when_llm_fails() -> None:
    state = create_world_state("magic_academy")
    llm = FakeLLM(RuntimeError("network down"))

    result = asyncio.run(
        build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(StageAction(ActionType.ASK_ACTOR, target="scholar")),
        )
    )

    assert not result.used_llm
    assert result.error == "network down"
    assert result.turn.queue.messages[0].speaker_role_id == "scholar"
    assert state.history[-1]["kind"] == "planner_fallback"
