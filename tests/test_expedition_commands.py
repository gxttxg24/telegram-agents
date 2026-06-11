from __future__ import annotations

import asyncio
from types import SimpleNamespace

import tg_agent_bot.expedition.commands as commands


class FakeMessage:
    def __init__(self, text: str, reply_to_message=None, from_user=None) -> None:
        self.text = text
        self.replies: list[str] = []
        self.reply_to_message = reply_to_message
        self.from_user = from_user

    async def reply_text(self, text: str, **kwargs) -> None:
        self.replies.append(text)


class FakeControllerBot:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.sent.append({"chat_id": chat_id, "text": text, **kwargs})

    async def get_me(self):
        return SimpleNamespace(id=123, username="StageControllerBot")


class FakeDispatcher:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_turn(self, context, chat_id, state, turn) -> None:
        self.calls.append({"chat_id": chat_id, "state": state, "turn": turn})


class FakeLLM:
    async def json_reply(self, system_prompt, user_prompt, *, timeout_seconds=None):
        return {
            "scene_update": "The prints brighten as Mori compares them with a field lens.",
            "clues_added": ["lens-visible spiral grain"],
            "speaker_messages": [
                {
                    "role_id": "scholar",
                    "intent": "explain_dynamic_clue",
                    "text": "The dust has a spiral grain. That means it was shed recently.",
                }
            ],
            "buttons": [
                {
                    "label": "Compare spiral grain",
                    "action_type": "observe_clue",
                    "target": "spiral_grain",
                },
                {
                    "label": "Wait",
                    "action_type": "interrupt",
                    "target": "",
                },
            ],
        }


class FakeWorldLLM:
    async def json_reply(self, system_prompt, user_prompt, *, timeout_seconds=None):
        return {
            "name": "Mushroom Train Mystery",
            "world_type": "cozy_rail_expedition",
            "tone": "cozy, odd, investigative",
            "user_role": "guest conductor-apprentice",
            "starting_objective": "Find why carriage seven grows a new door every stop.",
            "location": "platform under the lantern caps",
            "ecology": ["ticket beetles", "lantern mushrooms"],
            "anomalies": ["new doors", "singing rails"],
            "risk_level": "low",
            "roles": [
                {"role_id": "mentor", "display_name": "Brass", "archetype": "conductor mentor"},
                {"role_id": "scholar", "display_name": "Spore", "archetype": "mycology scholar"},
                {"role_id": "scout", "display_name": "Switch", "archetype": "track scout"},
                {"role_id": "log", "display_name": "Stub", "archetype": "ticket recorder"},
                {"role_id": "guide", "display_name": "Moss", "archetype": "platform guide"},
            ],
            "rules": ["Never wake the sleeping timetable."],
            "opening_scene": "The train exhales warm fog and grows an extra brass handle.",
            "opening_narration": [
                "A bell rings under the platform, and carriage seven answers with a second door."
            ],
            "opening_messages": [
                {
                    "role_id": "mentor",
                    "text": "Carriage seven just changed shape in front of us. Keep your tickets visible.",
                },
                {
                    "role_id": "scholar",
                    "text": "The new handle is warm, which means the door grew recently.",
                },
            ],
            "initial_clues": ["new brass handle", "warm fog"],
            "action_buttons": ["Inspect handle", "Ask Spore", "Send Switch ahead", "Board carriage seven"],
        }


class FakeCallbackQuery:
    def __init__(self, data: str, chat_id: int = 7001) -> None:
        self.data = data
        self.message = SimpleNamespace(chat_id=chat_id)
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


def fake_update(
    text: str,
    chat_id: int = 7001,
    chat_type: str = "group",
    reply_to_message=None,
    from_user=None,
):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id, type=chat_type),
        effective_message=FakeMessage(
            text,
            reply_to_message=reply_to_message,
            from_user=from_user,
        ),
    )


def fake_callback_update(data: str, chat_id: int = 7001):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id, type="group"),
        effective_message=None,
        callback_query=FakeCallbackQuery(data, chat_id),
    )


def fake_context():
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={}),
        bot=FakeControllerBot(),
    )


def test_expedition_start_stores_world_and_uses_dispatcher(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    update = fake_update("/expedition_start magic_academy")
    context = fake_context()

    asyncio.run(commands.expedition_start(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    assert state.world_pack.name == "Starcedar Academy: Mistfeather Grove Night Observation"
    assert "Expedition started" in update.effective_message.replies[0]
    assert dispatcher.calls[0]["chat_id"] == 7001
    assert [message.speaker_role_id for message in dispatcher.calls[0]["turn"].queue.messages] == [
        "mentor",
        "scholar",
    ]


def test_expedition_start_private_chat_explains_group_requirement(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    update = fake_update("/expedition_start magic_academy", chat_type="private")
    context = fake_context()

    asyncio.run(commands.expedition_start(update, context))

    assert "must be started inside the Telegram group" in update.effective_message.replies[0]
    assert "expedition_worlds" not in context.application.bot_data
    assert dispatcher.calls == []


def test_expedition_start_generates_custom_world_with_llm(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    update = fake_update("/expedition_start cozy mushroom train mystery")
    context = fake_context()
    context.application.bot_data["llm"] = FakeWorldLLM()

    asyncio.run(commands.expedition_start(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    assert state.world_pack.name == "Mushroom Train Mystery"
    assert "Expedition started: Mushroom Train Mystery" in update.effective_message.replies[0]
    assert dispatcher.calls[0]["turn"].queue.messages[0].speaker_role_id == "mentor"
    assert dispatcher.calls[0]["turn"].queue.messages[0].text == (
        "Carriage seven just changed shape in front of us. Keep your tickets visible."
    )
    assert dispatcher.calls[0]["turn"].narration == [
        "A bell rings under the platform, and carriage seven answers with a second door."
    ]


def test_expedition_start_uses_fallback_world_without_llm(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    update = fake_update("/expedition_start cozy mushroom train mystery")
    context = fake_context()

    asyncio.run(commands.expedition_start(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    assert state.world_pack.world_type == "generated_fallback"
    assert "no LLM client is configured" in update.effective_message.replies[0]


def test_expedition_group_text_records_user_action(monkeypatch) -> None:
    context = fake_context()
    start_update = fake_update("/expedition_start magic_academy")
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )

    asyncio.run(commands.expedition_start(start_update, context))

    update = fake_update("I ask Mori about the dust.")
    asyncio.run(commands.expedition_group_text(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    assert state.history[-1]["kind"] == "user_action"
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "scholar"


def test_expedition_group_text_ignores_bot_messages(monkeypatch) -> None:
    context = fake_context()
    start_update = fake_update("/expedition_start magic_academy")
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )

    asyncio.run(commands.expedition_start(start_update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    history_count = len(state.history)
    dispatch_count = len(dispatcher.calls)
    update = fake_update(
        "Ailo:\nI can turn this into a field terminal.",
        from_user=SimpleNamespace(is_bot=True, username="AiloBot"),
    )
    asyncio.run(commands.expedition_group_text(update, context))

    assert len(state.history) == history_count
    assert len(dispatcher.calls) == dispatch_count


def test_expedition_role_command_routes_to_named_actor(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    asyncio.run(commands.expedition_start(fake_update("/expedition_start magic_academy"), context))

    update = fake_update("/mori What do you think about this dust?")
    asyncio.run(commands.expedition_role_command(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    user_action = [event for event in state.history if event["kind"] == "user_action"][-1]
    assert user_action["addressed_role"] == "scholar"
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "scholar"


def test_expedition_role_command_handles_mori_computer_pivot(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    asyncio.run(commands.expedition_start(fake_update("/expedition_start magic_academy"), context))

    update = fake_update(
        "/mori What about turning mori into a computer and let chatgpt analyse the scene?"
    )
    asyncio.run(commands.expedition_role_command(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    user_action = [event for event in state.history if event["kind"] == "user_action"][-1]
    assert user_action["category"] == "major_pivot"
    assert user_action["addressed_role"] == "scholar"
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "scholar"


def test_expedition_free_action_command_handles_major_pivot(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    asyncio.run(commands.expedition_start(fake_update("/expedition_start magic_academy"), context))

    update = fake_update(
        "/do What about turning ailo into a computer and let chatgpt analyse the scene?"
    )
    asyncio.run(commands.expedition_free_action_command(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    user_action = [event for event in state.history if event["kind"] == "user_action"][-1]
    assert user_action["category"] == "major_pivot"
    assert state.active_objective.title == (
        "Create a Mistfeather Grove environmental anomaly field report."
    )
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "guide"


def test_expedition_free_action_command_requires_text(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    asyncio.run(commands.expedition_start(fake_update("/expedition_start magic_academy"), context))

    update = fake_update("/do")
    asyncio.run(commands.expedition_free_action_command(update, context))

    assert "Say what you want to do" in update.effective_message.replies[0]


def test_expedition_group_text_reply_to_actor_routes_to_role(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    context.application.bot_data.update(
        {
            "bot_peers": {"B": "@MoriBot"},
            "expedition_role_profiles": {"scholar": "B"},
        }
    )
    asyncio.run(commands.expedition_start(fake_update("/expedition_start magic_academy"), context))

    replied = SimpleNamespace(from_user=SimpleNamespace(username="MoriBot"))
    update = fake_update("Could it be dangerous?", reply_to_message=replied)
    asyncio.run(commands.expedition_group_text(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    user_action = [event for event in state.history if event["kind"] == "user_action"][-1]
    assert user_action["addressed_role"] == "scholar"
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "scholar"


def test_expedition_group_text_handles_dangerous_absurd_action(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    start_update = fake_update("/expedition_start magic_academy")
    asyncio.run(commands.expedition_start(start_update, context))

    update = fake_update("我要引发沼气爆炸把我们全送上天探索天堂")
    asyncio.run(commands.expedition_group_text(update, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    user_action = [event for event in state.history if event["kind"] == "user_action"][-1]
    assert user_action["category"] == "dangerous_absurd_pivot"
    assert "cloud wetland" in state.scene
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "scout"


def test_expedition_debug_reports_profiles_without_tokens() -> None:
    context = fake_context()
    context.application.bot_data.update(
        {
            "bot_profile": "C",
            "bot_tokens": {"A": "secret-token-a", "C": "secret-token-c"},
            "bot_peers": {"A": "@MentorBot", "C": "@StageControllerBot"},
            "expedition_role_profiles": {"controller": "C", "mentor": "A"},
        }
    )
    update = fake_update("/expedition_debug")

    asyncio.run(commands.expedition_debug(update, context))

    text = update.effective_message.replies[0]
    assert "getMe: @StageControllerBot" in text
    assert "mentor: profile A -> @MentorBot [ok]" in text
    assert "secret-token" not in text


def test_expedition_knowledge_reports_current_ledger(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    asyncio.run(commands.expedition_start(fake_update("/expedition_start magic_academy"), context))

    update = fake_update("/expedition_knowledge")
    asyncio.run(commands.expedition_knowledge(update, context))

    text = update.effective_message.replies[0]
    assert text.startswith("expedition knowledge")
    assert "location: Mistfeather Grove wetland entrance" in text
    assert "blue glowing footprints" in text


def test_expedition_action_callback_dispatches_controlled_action(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    start_update = fake_update("/expedition_start magic_academy")
    asyncio.run(commands.expedition_start(start_update, context))
    callback = fake_callback_update("expedition:action:observe_clue:footprints")

    asyncio.run(commands.expedition_action_callback(callback, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    assert callback.callback_query.answered
    assert state.history[-1]["kind"] in {"button_action", "clue"}
    assert "moon-reactive scale dust" in state.clues
    assert dispatcher.calls[-1]["turn"].user_action == "observe_clue:footprints"
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "scholar"


def test_expedition_action_callback_uses_llm_planner_when_available(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    context.application.bot_data["llm"] = FakeLLM()
    start_update = fake_update("/expedition_start magic_academy")
    asyncio.run(commands.expedition_start(start_update, context))
    callback = fake_callback_update("expedition:action:observe_clue:footprints")

    asyncio.run(commands.expedition_action_callback(callback, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    assert "lens-visible spiral grain" in state.clues
    assert state.world_pack.action_buttons[0] == "Compare spiral grain"
    assert state.world_pack.action_buttons[-1] == "Wait"
    assert len(state.world_pack.action_buttons) == 5
    assert dispatcher.calls[-1]["turn"].queue.messages[0].text.startswith("The dust has")


def test_expedition_action_callback_wait_enters_interrupt_state(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    start_update = fake_update("/expedition_start magic_academy")
    asyncio.run(commands.expedition_start(start_update, context))
    callback = fake_callback_update("expedition:action:interrupt")

    asyncio.run(commands.expedition_action_callback(callback, context))

    state = context.application.bot_data["expedition_worlds"][7001]
    assert callback.callback_query.answered
    assert state.flags["stage_status"] == "user_interrupting"
    assert "Stage paused" in context.bot.sent[-1]["text"]


def test_expedition_action_callback_handles_proposal_choice_without_llm(monkeypatch) -> None:
    dispatcher = FakeDispatcher()
    monkeypatch.setattr(
        commands.StageDispatcher,
        "from_context",
        classmethod(lambda cls, context: dispatcher),
    )
    context = fake_context()
    asyncio.run(commands.expedition_start(fake_update("/expedition_start magic_academy"), context))
    state = context.application.bot_data["expedition_worlds"][7001]
    state.world_pack.action_buttons = ["Take Raven's lift-current route", "Wait"]
    state.flags["button_actions"] = {
        "Take Raven's lift-current route": "expedition:action:choose_proposal:scout_bold",
        "Wait": "expedition:action:interrupt",
    }
    callback = fake_callback_update("expedition:action:choose_proposal:scout_bold")

    asyncio.run(commands.expedition_action_callback(callback, context))

    assert callback.callback_query.answered
    assert state.history[-1]["kind"] == "proposal_chosen"
    assert dispatcher.calls[-1]["turn"].queue.messages[0].speaker_role_id == "scout"
