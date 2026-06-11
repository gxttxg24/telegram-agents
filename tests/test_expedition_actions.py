from __future__ import annotations

from tg_agent_bot.expedition.actions import ActionType, StageAction, action_for_button


def test_action_for_button_maps_labels_to_controlled_semantics() -> None:
    assert action_for_button("Inspect footprints") == StageAction(
        ActionType.OBSERVE_CLUE,
        target="footprints",
        label="Inspect footprints",
    )
    assert action_for_button("检查足迹").semantic_key == "observe_clue:footprints"
    assert action_for_button("Ask Mori").semantic_key == "ask_actor:scholar"
    assert action_for_button("询问学者").semantic_key == "ask_actor:scholar"
    assert action_for_button("Send Raven ahead").semantic_key == "assist_actor:scout"
    assert action_for_button("前往旧瞭望塔").semantic_key == "move_location:old_watchtower"
    assert action_for_button("等等").semantic_key == "interrupt"
    assert action_for_button("恢复原探险").semantic_key == "resume_objective"
    assert action_for_button("生成 PPT 大纲").semantic_key == (
        "generate_report_outline:ppt_outline"
    )
    assert action_for_button("采纳 Raven 的冒险路线").semantic_key == (
        "choose_proposal:synthesis"
    )


def test_stage_action_callback_round_trip() -> None:
    action = StageAction(ActionType.CHOOSE_PROPOSAL, target="scout_bold")

    parsed = StageAction.from_callback_data(action.to_callback_data())

    assert parsed == action
    assert action.to_callback_data() == "expedition:action:choose_proposal:scout_bold"


def test_stage_action_rejects_unknown_callbacks() -> None:
    assert StageAction.from_callback_data("other:action:ask_actor:scholar") is None
    assert StageAction.from_callback_data("expedition:action:unknown") is None
