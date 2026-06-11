from __future__ import annotations

from tg_agent_bot.expedition.stage import (
    action_keyboard,
    build_opening_turn,
    button_action,
    format_actor_message,
    format_controller_opening,
)
from tg_agent_bot.expedition.generator import generate_world_state
from tg_agent_bot.expedition.templates import create_world_state


def test_opening_turn_contains_only_visible_actor_messages() -> None:
    state = create_world_state("magic_academy")
    turn = build_opening_turn(state)

    assert state.turn_number == 1
    assert [message.speaker_role_id for message in turn.queue.messages] == [
        "mentor",
        "scholar",
    ]


def test_controller_opening_is_not_director_character_speech() -> None:
    state = create_world_state("magic_academy")

    text = format_controller_opening(state)

    assert text.startswith("Expedition started:")
    assert "DirectorBot:" not in text
    assert "Location:" in text


def test_actor_formatting_and_buttons() -> None:
    state = create_world_state("magic_academy")
    turn = build_opening_turn(state)

    assert format_actor_message(state, turn.queue.messages[0]).startswith("Serena:")
    keyboard = action_keyboard(state)
    assert keyboard.inline_keyboard[0][0].text == "Inspect footprints"
    assert keyboard.inline_keyboard[0][0].callback_data == (
        "expedition:action:observe_clue:footprints"
    )
    assert button_action("Wait") == "interrupt"


def test_generated_chinese_world_uses_chinese_opening_and_panel() -> None:
    import asyncio

    state = asyncio.run(generate_world_state(None, "我想玩一个月亮菜市场")).state
    opening = format_controller_opening(state)
    turn = build_opening_turn(state)

    assert opening.startswith("远征开始：")
    assert "地点：" in opening
    assert "目标：" in opening
    assert "目标很清楚" not in turn.queue.messages[0].text
    assert turn.queue.messages[0].text == "先别散开。这里有东西已经开始回应我们了。"
    assert turn.queue.messages[1].text == "我会看它接下来怎么变化；第二个证据通常来得很快。"
    assert turn.narration == ["空气突然安静下来，队伍意识到这个地方正在等待第一个决定。"]
    assert "守住边界" not in turn.queue.messages[0].text
    assert "磨平" not in turn.queue.messages[0].text
    assert action_keyboard(state).inline_keyboard[-1][0].callback_data == (
        "expedition:action:interrupt"
    )


def test_generated_english_world_opening_hides_director_policy() -> None:
    import asyncio

    state = asyncio.run(generate_world_state(None, "moon market")).state
    turn = build_opening_turn(state)

    assert "I will keep the expedition bounded" not in turn.queue.messages[0].text
    assert "sand the strangeness" not in turn.queue.messages[0].text
    assert "Start with the visible clues" not in turn.queue.messages[0].text
    assert turn.queue.messages[0].text == "Stay close. Something here has already started answering us."
    assert turn.queue.messages[1].text == (
        "I will watch what changes next; the second piece of evidence usually arrives quickly."
    )
    assert turn.narration == [
        "The air goes quiet, and the group realizes the place is waiting for the first choice."
    ]
