from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tg_agent_bot.expedition.bot_pool import BotPool, RoleAssignment
from tg_agent_bot.expedition.dispatcher import StageDispatcher
from tg_agent_bot.expedition.models import StageMessage, StageTurn
from tg_agent_bot.expedition.stage import build_opening_turn
from tg_agent_bot.expedition.templates import create_world_state


class FakeActorSender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, profile: str, chat_id: int, text: str) -> None:
        self.sent.append({"profile": profile, "chat_id": chat_id, "text": text})


class FakeControllerBot:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.sent.append({"chat_id": chat_id, "text": text, **kwargs})


def fake_context(bot_data: dict | None = None):
    return SimpleNamespace(
        application=SimpleNamespace(bot_data=bot_data or {}),
        bot=FakeControllerBot(),
    )


def test_bot_pool_loads_actor_identities_from_bot_data() -> None:
    pool = BotPool.from_bot_data(
        {
            "bot_tokens": {"A": "token-a", "B": "token-b"},
            "bot_peers": {"A": "@MentorBot", "B": "@ScholarBot"},
        }
    )

    assert pool.get("a").username == "@MentorBot"
    assert pool.get("B").token == "token-b"
    assert pool.get("C") is None


def test_stage_dispatcher_sends_actor_messages_through_assigned_profiles() -> None:
    state = create_world_state("magic_academy")
    turn = build_opening_turn(state)
    sender = FakeActorSender()
    dispatcher = StageDispatcher(
        role_assignment=RoleAssignment({"mentor": "A", "scholar": "B"}),
        sender=sender,
    )
    context = fake_context()

    asyncio.run(dispatcher.send_turn(context, 9001, state, turn))

    assert [item["profile"] for item in sender.sent] == ["A", "B"]
    assert sender.sent[0]["text"].startswith("Serena:")
    assert sender.sent[1]["text"].startswith("Mori:")
    assert len(context.bot.sent) == 1
    assert context.bot.sent[0]["reply_markup"].inline_keyboard[-1][0].callback_data == (
        "expedition:action:interrupt"
    )


def test_stage_dispatcher_sends_narration_before_actor_messages() -> None:
    state = create_world_state("magic_academy")
    turn = StageTurn.create(
        epoch=state.epoch,
        user_action="observe_clue:storm",
        narration=["A sudden rainstorm turns the reed path into a silver mirror."],
        messages=[
            StageMessage(
                speaker_role_id="scout",
                text="The mirror-path shows a safe edge. I can mark it before we move.",
                intent="react_to_narration",
                epoch=state.epoch,
            )
        ],
        buttons=["Wait"],
    )
    sender = FakeActorSender()
    dispatcher = StageDispatcher(
        role_assignment=RoleAssignment({"scout": "C"}),
        sender=sender,
    )
    context = fake_context()

    asyncio.run(dispatcher.send_turn(context, 9001, state, turn))

    assert context.bot.sent[0]["text"].startswith("A sudden rainstorm")
    assert sender.sent[0]["profile"] == "C"
    assert sender.sent[0]["text"].startswith("Raven:")
    assert context.bot.sent[-1]["reply_markup"].inline_keyboard[-1][0].callback_data == (
        "expedition:action:interrupt"
    )
