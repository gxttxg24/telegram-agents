from __future__ import annotations

from tg_agent_bot.expedition.compiler import compile_user_action
from tg_agent_bot.expedition.director import build_turn_for_compiled_action
from tg_agent_bot.expedition.models import ObjectiveStatus
from tg_agent_bot.expedition.templates import create_world_state


def test_dangerous_absurd_turn_uses_safe_world_rewrite() -> None:
    state = create_world_state("magic_academy")
    compiled = compile_user_action(
        state,
        "I want to make methane explode and send us into the sky to explore heaven.",
    )

    turn = build_turn_for_compiled_action(state, compiled)

    assert "cloud wetland" in state.scene
    assert "controlled marsh-spirit lift" in state.clues
    assert [message.speaker_role_id for message in turn.queue.messages] == [
        "scout",
        "mentor",
        "scholar",
    ]
    assert "sky idea is excellent" in turn.queue.messages[0].text
    assert "Anchor charms" in turn.queue.messages[1].text
    assert "No explosions" not in turn.queue.messages[1].text
    assert "But" not in turn.queue.messages[1].text
    assert state.world_pack.action_buttons[0] == "Take Raven's lift-current route"
    assert state.flags["button_actions"]["Take Raven's lift-current route"] == (
        "expedition:action:choose_proposal:scout_bold"
    )


def test_conceptual_error_turn_offers_playable_alternatives() -> None:
    state = create_world_state("magic_academy")
    compiled = compile_user_action(
        state,
        "Write enough H and O to get water in the desert.",
    )

    turn = build_turn_for_compiled_action(state, compiled)

    assert turn.queue.messages[0].speaker_role_id == "scholar"
    assert "symbols, not water" in turn.queue.messages[0].text
    assert turn.queue.messages[1].speaker_role_id == "guide"
    assert state.world_pack.action_buttons == [
        "Try Ailo's locator sigil",
        "Ask Mori for the rule",
        "Use Serena's dewstone route",
        "Let Pip pick a test",
        "Wait",
    ]


def test_major_pivot_pushes_new_objective_and_report_buttons() -> None:
    state = create_world_state("magic_academy")
    old_objective = state.active_objective
    compiled = compile_user_action(
        state,
        "Turn the guide into a computer and make a field report PPT for the mentor.",
    )

    turn = build_turn_for_compiled_action(state, compiled)

    assert old_objective.status is ObjectiveStatus.PAUSED
    assert state.active_objective.title == (
        "Create a Mistfeather Grove environmental anomaly field report."
    )
    assert [message.speaker_role_id for message in turn.queue.messages] == [
        "guide",
        "mentor",
    ]
    assert turn.narration == [
        "Compromise logged: convert current clues into a field report workflow, then choose whether to return to the footprints."
    ]
    assert state.world_pack.action_buttons[0] == "Use Ailo as field terminal"
    assert state.flags["button_actions"]["Use Ailo as field terminal"] == (
        "expedition:action:choose_proposal:guide_weird"
    )


def test_major_pivot_addressed_to_mori_starts_with_scholar() -> None:
    state = create_world_state("magic_academy")
    compiled = compile_user_action(
        state,
        "What about turning mori into a computer and let chatgpt analyse the scene?",
        addressed_role="scholar",
    )

    turn = build_turn_for_compiled_action(state, compiled)

    assert turn.queue.messages[0].speaker_role_id == "scholar"
    assert "read this scene from our clues" in turn.queue.messages[0].text
    assert "plugin" not in turn.queue.messages[0].text.casefold()
    assert "but" not in turn.queue.messages[0].text.casefold()
    assert not any(message.speaker_role_id == "log" for message in turn.queue.messages)
    assert turn.narration == [
        "Objective reframed: build a scene analysis from footprints, scale dust, humidity, and watchtower wind patterns."
    ]
