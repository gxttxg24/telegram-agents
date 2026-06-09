from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WeatherScheduleStage(StrEnum):
    WEATHER = "weather"
    CALENDAR = "calendar"
    SLOT_MATCHER = "slot_matcher"
    ADD_EVENT = "add_event"


class WeatherScheduleNext(StrEnum):
    SEND_WEATHER = "send_weather"
    SEND_CALENDAR = "send_calendar"
    SEND_SLOT_MATCHER = "send_slot_matcher"
    FINISH = "finish"
    MESSAGE = "message"


@dataclass
class WeatherScheduleTransition:
    next_step: WeatherScheduleNext
    message: str | None = None


@dataclass
class WeatherScheduleState:
    user_chat_id: int
    user_text: str
    goal: str
    activity_title: str
    duration_minutes: int
    rain_threshold: int
    actions: list[dict[str, Any]]
    index: int = 0
    stage: WeatherScheduleStage = WeatherScheduleStage.WEATHER
    results: list[dict[str, Any]] = field(default_factory=list)
    weather_results: list[dict[str, Any]] = field(default_factory=list)
    calendar_results: list[dict[str, Any]] = field(default_factory=list)
    selected_match: dict[str, Any] | None = None

    @classmethod
    def from_plan(
        cls,
        *,
        user_chat_id: int,
        user_text: str,
        plan: dict[str, Any],
    ) -> WeatherScheduleState:
        return cls(
            user_chat_id=user_chat_id,
            user_text=user_text,
            goal=str(plan.get("goal", "forecast")),
            activity_title=str(plan.get("activity_title") or "天气相关安排"),
            duration_minutes=int(plan.get("duration_minutes") or 60),
            rain_threshold=30,
            actions=_list_of_dicts(plan["actions"]),
        )

    def current_action(self) -> dict[str, Any]:
        return dict(self.actions[self.index])

    def has_next_action(self) -> bool:
        return self.index < len(self.actions) - 1

    def advance_index(self) -> None:
        self.index += 1

    def start_stage(
        self,
        stage: WeatherScheduleStage,
        actions: list[dict[str, Any]],
    ) -> None:
        self.stage = stage
        self.actions = actions
        self.index = 0


# REVIEW: 这个函数只是调了一下 WeatherScheduleState.from_plan()，没有任何额外逻辑。
# 函数 -> classmethod -> __init__，三层间接才构造一个对象，AI 生成的"整洁代码"典型。
# 直接在调用方写 WeatherScheduleState.from_plan(...) 就行，删掉这个 wrapper。
def build_weather_schedule_workflow(
    *,
    user_chat_id: int,
    user_text: str,
    plan: dict[str, Any],
) -> WeatherScheduleState:
    return WeatherScheduleState.from_plan(
        user_chat_id=user_chat_id,
        user_text=user_text,
        plan=plan,
    )


def advance_weather_schedule(
    state: WeatherScheduleState,
    payload: dict[str, Any],
) -> WeatherScheduleTransition:
    if payload.get("ok") is not True:
        return WeatherScheduleTransition(
            WeatherScheduleNext.MESSAGE,
            f"工作流在 {state.stage.value} 阶段失败：{payload.get('error') or '未知错误'}",
        )

    if state.stage is WeatherScheduleStage.WEATHER:
        return _advance_weather_stage(state, payload)

    if state.stage is WeatherScheduleStage.CALENDAR:
        return _advance_calendar_stage(state, payload)

    if state.stage is WeatherScheduleStage.SLOT_MATCHER:
        return _advance_slot_matcher_stage(state, payload)

    if state.stage is WeatherScheduleStage.ADD_EVENT:
        return WeatherScheduleTransition(WeatherScheduleNext.FINISH)

    return WeatherScheduleTransition(
        WeatherScheduleNext.MESSAGE,
        f"未知工作流阶段：{state.stage.value}",
    )


# REVIEW: 公开函数只是调了同名的私有函数，零附加价值。直接把 _build_slot_matcher_payload 改成公开的。
def build_slot_matcher_payload(state: WeatherScheduleState) -> dict[str, Any] | None:
    return _build_slot_matcher_payload(state)


def _advance_weather_stage(
    state: WeatherScheduleState,
    payload: dict[str, Any],
) -> WeatherScheduleTransition:
    state.weather_results.append(payload)
    if state.has_next_action():
        state.advance_index()
        return WeatherScheduleTransition(WeatherScheduleNext.SEND_WEATHER)

    calendar_actions = _calendar_actions_from_weather(state)
    if not calendar_actions:
        return WeatherScheduleTransition(
            WeatherScheduleNext.MESSAGE,
            "天气查询完成，但没有拿到可用日期。",
        )
    state.start_stage(WeatherScheduleStage.CALENDAR, calendar_actions)
    return WeatherScheduleTransition(WeatherScheduleNext.SEND_CALENDAR)


def _advance_calendar_stage(
    state: WeatherScheduleState,
    payload: dict[str, Any],
) -> WeatherScheduleTransition:
    state.calendar_results.append(payload)
    if state.has_next_action():
        state.advance_index()
        return WeatherScheduleTransition(WeatherScheduleNext.SEND_CALENDAR)

    matcher_payload = _build_slot_matcher_payload(state)
    if matcher_payload is None:
        return WeatherScheduleTransition(
            WeatherScheduleNext.MESSAGE,
            "没有拿到可匹配的天气时段或空闲时间。",
        )
    state.start_stage(WeatherScheduleStage.SLOT_MATCHER, [matcher_payload])
    return WeatherScheduleTransition(WeatherScheduleNext.SEND_SLOT_MATCHER)


def _advance_slot_matcher_stage(
    state: WeatherScheduleState,
    payload: dict[str, Any],
) -> WeatherScheduleTransition:
    matches = payload.get("matches") or []
    if not matches:
        return WeatherScheduleTransition(
            WeatherScheduleNext.MESSAGE,
            "我综合天气和你的空闲时间后，没有找到合适的共同时间段。",
        )

    match = matches[0]
    if not isinstance(match, dict):
        return WeatherScheduleTransition(
            WeatherScheduleNext.MESSAGE,
            "我综合天气和你的空闲时间后，没有找到合适的共同时间段。",
        )

    state.selected_match = match
    state.start_stage(
        WeatherScheduleStage.ADD_EVENT,
        [
            {
                "action": "add_event",
                "title": state.activity_title,
                "starts_at": match["starts_at"],
                "ends_at": match["ends_at"],
                "on_conflict": "reject",
            }
        ],
    )
    return WeatherScheduleTransition(WeatherScheduleNext.SEND_CALENDAR)


def _calendar_actions_from_weather(
    state: WeatherScheduleState,
) -> list[dict[str, Any]]:
    return [
        {
            "action": "free_time",
            "date": result.get("date"),
            "min_duration_minutes": state.duration_minutes,
        }
        for result in state.weather_results
        if result.get("date")
    ]


def _build_slot_matcher_payload(
    state: WeatherScheduleState,
) -> dict[str, Any] | None:
    weather_periods: list[dict[str, Any]] = []
    for result in state.weather_results:
        for period in result.get("periods") or []:
            if isinstance(period, dict):
                weather_periods.append(period)

    calendar_blocks: list[dict[str, Any]] = []
    for result in state.calendar_results:
        for block in result.get("blocks") or []:
            if isinstance(block, dict):
                calendar_blocks.append(block)

    if not weather_periods or not calendar_blocks:
        return None

    return {
        "action": "match_slots",
        "goal": state.goal,
        "duration_minutes": state.duration_minutes,
        "rain_threshold": state.rain_threshold,
        "weather_periods": weather_periods,
        "calendar_blocks": calendar_blocks,
    }


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
