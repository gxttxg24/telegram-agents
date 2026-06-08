from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import tg_agent_bot.orchestrator.workflows as workflows
from tg_agent_bot.b2b.protocol import ACK, B2BEnvelope, parse_envelope
from tg_agent_bot.orchestrator.state import ActionWorkflow, WorkflowService
from tg_agent_bot.orchestrator.weather_schedule import (
    WeatherScheduleStage,
    WeatherScheduleState,
    WeatherScheduleNext,
    advance_weather_schedule,
    build_weather_schedule_workflow,
)


class FakeMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class FakeBot:
    def __init__(self, username: str = "OrchestratorBot") -> None:
        self.username = username
        self.sent_messages: list[dict] = []
        self.chat_actions: list[dict] = []

    async def get_me(self):
        return SimpleNamespace(id=12345, username=self.username)

    async def send_message(self, chat_id, text: str):
        self.sent_messages.append({"chat_id": chat_id, "text": text})
        return SimpleNamespace(message_id=len(self.sent_messages))

    async def send_chat_action(self, chat_id, action) -> None:
        self.chat_actions.append({"chat_id": chat_id, "action": action})


def fake_context(bot_data: dict | None = None, bot: FakeBot | None = None):
    data = {
        "bot_profile": "C",
        "orchestrator_profile": "C",
        "calendar_bot_profile": "A",
        "weather_bot_profile": "B",
        "slot_matcher_bot_profile": "D",
        "bot_peers": {
            "A": "@CalendarBot",
            "B": "@WeatherBot",
            "C": "@OrchestratorBot",
            "D": "@SlotMatcherBot",
        },
    }
    if bot_data:
        data.update(bot_data)
    return SimpleNamespace(
        application=SimpleNamespace(bot_data=data),
        bot=bot or FakeBot(),
    )


def fake_update(chat_id: int = 1001):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_message=FakeMessage(),
    )


def ack_envelope(correlation_id: str, payload: dict) -> B2BEnvelope:
    return B2BEnvelope(
        id=f"ack-{correlation_id}",
        message_type=ACK,
        source="@CalendarBot",
        target="@OrchestratorBot",
        conversation_id="conversation-id",
        correlation_id=correlation_id,
        payload=payload,
        depth=1,
        max_depth=1,
    )


def test_is_orchestrator_bot_checks_profile() -> None:
    assert workflows.is_orchestrator_bot(fake_context())
    assert not workflows.is_orchestrator_bot(fake_context({"bot_profile": "A"}))
    assert not workflows.is_orchestrator_bot(fake_context({"bot_profile": ""}))


def test_looks_like_weather_request_accepts_common_chinese_terms() -> None:
    assert workflows.looks_like_weather_request("上海明天会下雨吗")
    assert workflows.looks_like_weather_request("帮我看看天气")
    assert not workflows.looks_like_weather_request("明天下午两点开会")


def test_build_slot_matcher_payload_combines_weather_and_calendar_results() -> None:
    workflow = WeatherScheduleState(
        user_chat_id=1001,
        user_text="安排打球",
        goal="avoid_rain",
        activity_title="打球",
        duration_minutes=90,
        rain_threshold=40,
        actions=[{"action": "match_slots"}],
        weather_results=[
            {
                "periods": [
                    {
                        "starts_at": "2099-06-10T09:00",
                        "ends_at": "2099-06-10T12:00",
                        "max_precipitation_probability": 10,
                    }
                ]
            }
        ],
        calendar_results=[
            {
                "blocks": [
                    {
                        "starts_at": "2099-06-10T10:00:00+08:00",
                        "ends_at": "2099-06-10T12:00:00+08:00",
                    }
                ]
            }
        ],
    )

    payload = workflows.build_slot_matcher_payload(
        workflow
    )

    assert payload == {
        "action": "match_slots",
        "goal": "avoid_rain",
        "duration_minutes": 90,
        "rain_threshold": 40,
        "weather_periods": [
            {
                "starts_at": "2099-06-10T09:00",
                "ends_at": "2099-06-10T12:00",
                "max_precipitation_probability": 10,
            }
        ],
        "calendar_blocks": [
            {
                "starts_at": "2099-06-10T10:00:00+08:00",
                "ends_at": "2099-06-10T12:00:00+08:00",
            }
        ],
    }


def test_build_slot_matcher_payload_returns_none_without_inputs() -> None:
    workflow = WeatherScheduleState(
        user_chat_id=1001,
        user_text="安排打球",
        goal="avoid_rain",
        activity_title="打球",
        duration_minutes=90,
        rain_threshold=40,
        actions=[{"action": "match_slots"}],
    )

    assert workflows.build_slot_matcher_payload(workflow) is None


def test_weather_schedule_workflow_uses_typed_stage_transitions() -> None:
    workflow = build_weather_schedule_workflow(
        user_chat_id=1001,
        user_text="这周末找个不下雨的时间打球",
        plan={
            "goal": "avoid_rain",
            "activity_title": "打球",
            "duration_minutes": 120,
            "actions": [
                {"action": "hourly_forecast", "date": "2099-06-12"},
            ],
        },
    )

    transition = advance_weather_schedule(
        workflow,
        {
            "kind": "weather.result",
            "ok": True,
            "date": "2099-06-12",
            "periods": [{"starts_at": "2099-06-12T09:00", "ends_at": "2099-06-12T12:00"}],
        },
    )

    assert transition.next_step is WeatherScheduleNext.SEND_CALENDAR
    assert workflow.stage is WeatherScheduleStage.CALENDAR
    assert workflow.actions == [
        {
            "action": "free_time",
            "date": "2099-06-12",
            "min_duration_minutes": 120,
        }
    ]
    assert workflow.weather_results[0]["date"] == "2099-06-12"


def test_weather_schedule_slot_matcher_transition_builds_add_event_action() -> None:
    workflow = WeatherScheduleState(
        user_chat_id=1001,
        user_text="安排打球",
        goal="avoid_rain",
        activity_title="打球",
        duration_minutes=120,
        rain_threshold=30,
        actions=[{"action": "match_slots"}],
        stage=WeatherScheduleStage.SLOT_MATCHER,
    )

    transition = advance_weather_schedule(
        workflow,
        {
            "kind": "slot_matcher.result",
            "ok": True,
            "matches": [
                {
                    "starts_at": "2099-06-12T09:00:00+08:00",
                    "ends_at": "2099-06-12T11:00:00+08:00",
                    "max_precipitation_probability": 10,
                }
            ],
        },
    )

    assert transition.next_step is WeatherScheduleNext.SEND_CALENDAR
    assert workflow.stage is WeatherScheduleStage.ADD_EVENT
    assert workflow.selected_match is not None
    assert workflow.selected_match["max_precipitation_probability"] == 10
    assert workflow.actions == [
        {
            "action": "add_event",
            "title": "打球",
            "starts_at": "2099-06-12T09:00:00+08:00",
            "ends_at": "2099-06-12T11:00:00+08:00",
            "on_conflict": "reject",
        }
    ]


def test_send_orchestrator_calendar_action_sends_b2b_request_and_tracks_pending() -> None:
    bot = FakeBot()
    context = fake_context(bot=bot)
    workflow = ActionWorkflow.calendar(
        user_chat_id=1001,
        user_text="find free time",
        actions=[{"action": "free_time", "date": "2099-06-10"}],
    )

    asyncio.run(workflows.send_orchestrator_calendar_action(context, workflow))

    assert bot.sent_messages[0]["chat_id"] == "@CalendarBot"
    envelope = parse_envelope(bot.sent_messages[0]["text"])
    assert envelope is not None
    assert envelope.source == "@OrchestratorBot"
    assert envelope.target == "@CalendarBot"
    assert envelope.payload == {
        "action": "free_time",
        "date": "2099-06-10",
        "service": "calendar",
        "owner_chat_id": 1001,
    }
    assert context.application.bot_data["orchestrator_pending"][envelope.id] is workflow


def test_send_orchestrator_weather_action_requires_configured_peer() -> None:
    context = fake_context({"bot_peers": {"A": "@CalendarBot"}})
    workflow = ActionWorkflow.weather(
        user_chat_id=1001,
        user_text="weather",
        goal="forecast",
        actions=[{"action": "hourly_forecast", "date": "2099-06-10"}],
    )

    with pytest.raises(RuntimeError, match="WeatherBot profile B is not configured"):
        asyncio.run(workflows.send_orchestrator_weather_action(context, workflow))


def test_handle_orchestrator_b2b_result_continues_multi_step_calendar_workflow() -> None:
    bot = FakeBot()
    workflow = ActionWorkflow.calendar(
        user_chat_id=1001,
        user_text="schedule two things",
        actions=[
            {"action": "add_event", "title": "first"},
            {"action": "add_event", "title": "second"},
        ],
    )
    context = fake_context({"orchestrator_pending": {"req-1": workflow}}, bot)

    handled = asyncio.run(
        workflows.handle_orchestrator_b2b_result(
            context,
            ack_envelope("req-1", {"kind": "calendar.result", "ok": True}),
        )
    )

    assert handled is True
    assert workflow.index == 1
    assert workflow.results == [{"kind": "calendar.result", "ok": True}]
    envelope = parse_envelope(bot.sent_messages[0]["text"])
    assert envelope is not None
    assert envelope.payload["title"] == "second"
    assert envelope.id in context.application.bot_data["orchestrator_pending"]


def test_handle_orchestrator_b2b_result_ignores_unknown_or_unmatched_result() -> None:
    context = fake_context({"orchestrator_pending": {}})

    assert not asyncio.run(
        workflows.handle_orchestrator_b2b_result(
            context,
            ack_envelope("missing", {"kind": "calendar.result", "ok": True}),
        )
    )
    assert not asyncio.run(
        workflows.handle_orchestrator_b2b_result(
            context,
            ack_envelope("missing", {"kind": "other.result", "ok": True}),
        )
    )


def test_handle_orchestrator_text_starts_calendar_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_parse_calendar_plan(extract_llm, user_text: str, context: list[dict]):
        return {
            "ok": True,
            "summary": "calendar summary",
            "actions": [{"action": "add_event", "title": "meeting"}],
        }

    monkeypatch.setattr(workflows, "parse_calendar_plan", fake_parse_calendar_plan)
    update = fake_update()
    bot = FakeBot()
    context = fake_context({"extract_llm": object()}, bot)

    handled = asyncio.run(workflows.handle_orchestrator_text(update, context, "明天下午两点开会"))

    assert handled is True
    assert update.effective_message.replies == ["calendar summary"]
    assert bot.sent_messages
    envelope = parse_envelope(bot.sent_messages[0]["text"])
    assert envelope is not None
    assert envelope.payload["service"] == "calendar"


def test_handle_orchestrator_text_stores_pending_weather_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_parse_weather_plan(extract_llm, user_text: str):
        return {"ok": False, "ask_user": "请告诉我地点"}

    monkeypatch.setattr(workflows, "parse_weather_plan", fake_parse_weather_plan)
    update = fake_update()
    context = fake_context({"extract_llm": object()})

    handled = asyncio.run(workflows.handle_orchestrator_text(update, context, "明天会下雨吗"))

    assert handled is True
    assert update.effective_message.replies == ["请告诉我地点"]
    assert context.application.bot_data["orchestrator_pending_slots"][1001] == {
        "service": "weather",
        "original_text": "明天会下雨吗",
        "ask_user": "请告诉我地点",
    }


def test_finish_orchestrator_workflow_sends_calendar_summary_and_stores_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflows, "summarize_calendar_result", lambda result: "summary")
    monkeypatch.setattr(
        workflows,
        "calendar_context_from_result",
        lambda user_text, actions, results: {"user_text": user_text, "count": len(results)},
    )
    bot = FakeBot()
    context = fake_context(bot=bot)

    asyncio.run(
        workflows.finish_orchestrator_workflow(
            context,
            ActionWorkflow(
                service=WorkflowService.CALENDAR,
                user_chat_id=1001,
                user_text="add event",
                actions=[{"action": "add_event"}],
                results=[{"kind": "calendar.result", "ok": True}],
            ),
        )
    )

    assert bot.sent_messages == [{"chat_id": 1001, "text": "summary"}]
    assert context.application.bot_data["orchestrator_context_by_chat"][1001] == [
        {"user_text": "add event", "count": 1}
    ]
