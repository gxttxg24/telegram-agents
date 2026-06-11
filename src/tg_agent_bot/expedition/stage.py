from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .actions import action_for_button
from .knowledge import ensure_knowledge_ledger
from .models import StageMessage, StageTurn, WorldState


def build_opening_turn(state: WorldState) -> StageTurn:
    ensure_knowledge_ledger(state)
    epoch = state.epoch
    state.advance_turn()
    if state.world_pack.world_id == "starcedar-mistfeather-night-class":
        messages = [
            StageMessage(
                speaker_role_id="mentor",
                text=(
                    "Remember, tonight's assignment is observation, not capture. "
                    "You choose the first step, and I will keep the class inside safe limits."
                ),
                intent="set_safety_boundary",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="scholar",
                text=(
                    "The edge of each footprint carries a faint scale-dust reaction. "
                    "My first guess is a nocturnal magical reptile."
                ),
                intent="explain_initial_clue",
                epoch=epoch,
            ),
        ]
    else:
        messages = _generated_opening_messages(state, epoch)
    return StageTurn.create(
        epoch=epoch,
        user_action="start_expedition",
        messages=messages,
        narration=_opening_narration(state),
        buttons=list(state.world_pack.action_buttons),
    )


def _opening_narration(state: WorldState) -> list[str]:
    if state.world_pack.world_id == "starcedar-mistfeather-night-class":
        return []
    if state.world_pack.opening_narration:
        return list(state.world_pack.opening_narration[:2])
    if state.flags.get("language") == "zh":
        return ["空气突然安静下来，队伍意识到这个地方正在等待第一个决定。"]
    return ["The air goes quiet, and the group realizes the place is waiting for the first choice."]


def _generated_opening_messages(state: WorldState, epoch: int) -> list[StageMessage]:
    messages: list[StageMessage] = []
    for item in state.world_pack.opening_messages:
        role_id = item.get("role_id", "")
        text = item.get("text", "")
        if not role_id or not text or state.world_pack.role_by_id(role_id) is None:
            continue
        messages.append(
            StageMessage(
                speaker_role_id=role_id,
                text=text,
                intent="world_pack_opening_line",
                epoch=epoch,
            )
        )
        if len(messages) >= 2:
            break
    if messages:
        return messages
    if state.flags.get("language") == "zh":
        return [
            StageMessage(
                speaker_role_id="mentor",
                text="先别散开。这里有东西已经开始回应我们了。",
                intent="generated_opening_fallback",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="scholar",
                text="我会看它接下来怎么变化；第二个证据通常来得很快。",
                intent="generated_opening_fallback",
                epoch=epoch,
            ),
        ]
    return [
        StageMessage(
            speaker_role_id="mentor",
            text="Stay close. Something here has already started answering us.",
            intent="generated_opening_fallback",
            epoch=epoch,
        ),
        StageMessage(
            speaker_role_id="scholar",
            text="I will watch what changes next; the second piece of evidence usually arrives quickly.",
            intent="generated_opening_fallback",
            epoch=epoch,
        ),
    ]


def format_actor_message(state: WorldState, message: StageMessage) -> str:
    role = state.world_pack.role_by_id(message.speaker_role_id)
    if role is None:
        return message.text
    return f"{role.display_name}:\n{message.text}"


def format_controller_opening(state: WorldState) -> str:
    active = state.active_objective
    objective = active.title if active is not None else state.world_pack.starting_objective
    if state.flags.get("language") == "zh":
        return (
            f"远征开始：{state.world_pack.name}\n"
            f"第 {state.turn_number + 1} 回合\n"
            f"地点：{state.world_pack.location}\n"
            f"目标：{objective}\n\n"
            f"{state.scene}"
        )
    return (
        f"Expedition started: {state.world_pack.name}\n"
        f"Turn {state.turn_number + 1}\n"
        f"Location: {state.world_pack.location}\n"
        f"Objective: {objective}\n\n"
        f"{state.scene}"
    )


def format_action_panel(state: WorldState) -> str:
    active = state.active_objective
    objective = active.title if active is not None else state.world_pack.starting_objective
    if state.flags.get("language") == "zh":
        return (
            "轮到你行动。\n"
            f"目标：{objective}\n"
            "你可以点按钮、回复角色，或直接输入一句话。"
        )
    return (
        "Your move.\n"
        f"Objective: {objective}\n"
        "Choose an action, reply to a character, or type freely."
    )


def action_keyboard(state: WorldState) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            label,
            callback_data=_callback_data_for_button(state, label),
        )
        for label in state.world_pack.action_buttons[:5]
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def button_action(label: str) -> str:
    return action_for_button(label).semantic_key


def _callback_data_for_button(state: WorldState, label: str) -> str:
    mapping = state.flags.get("button_actions")
    if isinstance(mapping, dict):
        callback_data = mapping.get(label)
        if isinstance(callback_data, str) and callback_data.startswith("expedition:action:"):
            return callback_data
    return action_for_button(label).to_callback_data()
