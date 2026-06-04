from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from ...llm import LLMClient
from ...schedule import LOCAL_TZ


ORCHESTRATOR_SYSTEM_PROMPT = """
你是 Telegram 多 Agent 工作流的总控 JSON 规划器，只返回一个 JSON 对象，不要解释。
当前只处理日程/日历类请求。你不直接操作数据库，而是把用户自然语言转换为 CalendarBot 结构化 actions。

输出格式：
{
  "ok": true,
  "intent": "calendar",
  "summary": "简短中文说明",
  "actions": [
    {"action":"free_time","date":"YYYY-MM-DD","min_duration_minutes":120}
  ]
}

无法处理或信息不足：
{"ok":false,"error":"简短中文原因","ask_user":"需要追问用户的话"}

允许的 action 和字段：
1. list_events: {}
2. events_on_day: {"date":"YYYY-MM-DD"}
3. free_time: {"date":"YYYY-MM-DD","min_duration_minutes":可选整数}
4. add_event: {"title":"标题","starts_at":"YYYY-MM-DDTHH:MM:SS+08:00","ends_at":"YYYY-MM-DDTHH:MM:SS+08:00","on_conflict":"reject"}
5. schedule_event: {"title":"标题","date":"YYYY-MM-DD","duration_minutes":整数,"kind":"default|meal|lunch|dinner"}
6. delete_event: {"event_id":整数}
7. set_preference: {"preference":"用户偏好"}
8. get_preference: {}
9. move_event: {"event_id":可选整数,"title_contains":可选标题关键词,"date":可选YYYY-MM-DD,"shift_minutes":整数}
10. reschedule_event: {"event_id":可选整数,"title_contains":可选标题关键词,"from_date":可选YYYY-MM-DD,"to_date":"YYYY-MM-DD"}

规则：
- owner_chat_id/service 不要输出，程序会补。
- 今天/明天/后天/大后天必须根据用户提示中的日期表解析。
- “明天下午，大概两点开始组会，三点半结束” => add_event。
- “明天找时间打球2个小时” => schedule_event，title=打球，duration_minutes=120。
- “明天约朋友吃饭” => schedule_event，duration_minutes=90，kind=meal。
- “明天中午/午饭” kind=lunch；“晚上/晚饭/晚餐” kind=dinner。
- “查/看看/列一下日程” => list_events 或 events_on_day。
- “明天有空吗/空闲时间/什么时候有空” => free_time。
- “删除3号/删掉事件3” => delete_event。
- “我一般不想上午开会” => set_preference。
- “组会延后1小时/提前30分钟” => move_event，shift_minutes 正数为延后，负数为提前。若上下文有 event_id，优先用 event_id；否则用 title_contains 和 date。
- “刚刚说错了，不是明天，是后天”这类纠错：如果上下文能定位上一条事件，输出 reschedule_event，保留原时间。
- 如果用户说“同一时间/刚刚那个/上一条”，必须利用上下文里的 event id/title/date/time。
- 如果无法唯一定位要修改的事件，返回 ok=false 并追问，不要臆造 event_id。
- actions 最多 3 个。
""".strip()


WEATHER_SYSTEM_PROMPT = """
你是 Telegram 多 Agent 工作流的天气 JSON 规划器，只返回一个 JSON 对象，不要解释。
当前只处理天气/降水查询，不安排日程。

输出格式：
{
  "ok": true,
  "intent": "weather",
  "summary": "简短中文说明",
  "goal": "avoid_rain",
  "schedule_requested": true,
  "activity_title": "打球",
  "duration_minutes": 120,
  "location": "上海",
  "actions": [
    {"action":"hourly_forecast","location":"上海","date":"YYYY-MM-DD","country_code":"CN","timezone":"Asia/Shanghai","interval_hours":3}
  ]
}

信息缺失：
{"ok":false,"error":"简短中文原因","ask_user":"需要追问用户的话"}

规则：
- 只输出 WeatherBot 支持的 hourly_forecast action。
- 用户要求“不下雨/少雨/降水概率低/适合户外”，goal 使用 avoid_rain；否则 goal 使用 forecast。
- 用户要求“赏雨/看雨/淋雨/听雨/想找下雨时间”，goal 使用 prefer_rain。
- 如果用户只是询问天气/会不会下雨，不要求找时间或安排活动，schedule_requested=false。
- 如果用户要求“找个时间/安排/约/打球/赏雨”等需要后续排日程，schedule_requested=true。
- 如果用户提到活动，输出 activity_title，例如“打球”“赏雨”；没有活动就用“天气相关安排”。
- 如果用户提到时长，输出 duration_minutes；没有时长时，打球默认 120 分钟，赏雨默认 60 分钟，其它默认 60 分钟。
- 如果没有明确地点，必须返回 ok=false 并追问所在城市/地区。
- 如果没有明确日期或日期范围，必须返回 ok=false 并追问日期。
- 如果 user_text 中包含“用户补充信息：...”，请把补充信息和前面的原始请求合并理解；例如原始请求缺地点，补充信息“上海”就是 location=上海。
- “这周末/本周末”使用用户提示中的 this_weekend_dates，通常是本周六和本周日。
- “下周末”使用 next_weekend_dates。
- “明天/后天/大后天”必须根据用户提示中的日期表解析。
- 一个日期输出一个 action；日期范围最多输出 4 个 action。
- location 保持用户说的中文地名，例如“上海”“北京海淀”“杭州西湖区”。
- country_code 默认 CN，timezone 默认 Asia/Shanghai，interval_hours 默认 3。
- 不要输出自然语言解释。
""".strip()


async def parse_calendar_plan(
    llm: LLMClient,
    user_text: str,
    *,
    context: list[dict[str, Any]],
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    now = datetime.now(LOCAL_TZ)
    user_prompt = {
        "json_request": "Return a JSON object only.",
        "now": now.isoformat(),
        "today": now.date().isoformat(),
        "tomorrow": (now.date() + timedelta(days=1)).isoformat(),
        "after_tomorrow": (now.date() + timedelta(days=2)).isoformat(),
        "three_days_later": (now.date() + timedelta(days=3)).isoformat(),
        "timezone": "Asia/Shanghai UTC+08:00",
        "recent_calendar_context": context[-6:],
        "user_text": user_text,
    }
    data = await llm.json_reply(
        ORCHESTRATOR_SYSTEM_PROMPT,
        json.dumps(user_prompt, ensure_ascii=False),
        timeout_seconds=timeout_seconds,
    )
    return _validate_plan(data)


async def parse_weather_plan(
    llm: LLMClient,
    user_text: str,
    *,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    now = datetime.now(LOCAL_TZ)
    user_prompt = {
        "json_request": "Return a JSON object only.",
        "now": now.isoformat(),
        "today": now.date().isoformat(),
        "tomorrow": (now.date() + timedelta(days=1)).isoformat(),
        "after_tomorrow": (now.date() + timedelta(days=2)).isoformat(),
        "three_days_later": (now.date() + timedelta(days=3)).isoformat(),
        "this_weekend_dates": [item.isoformat() for item in _weekend_dates(now.date(), weeks_ahead=0)],
        "next_weekend_dates": [item.isoformat() for item in _weekend_dates(now.date(), weeks_ahead=1)],
        "timezone": "Asia/Shanghai UTC+08:00",
        "user_text": user_text,
    }
    data = await llm.json_reply(
        WEATHER_SYSTEM_PROMPT,
        json.dumps(user_prompt, ensure_ascii=False),
        timeout_seconds=timeout_seconds,
    )
    return _validate_weather_plan(data)


def summarize_calendar_result(payload: dict[str, Any]) -> str:
    action = str(payload.get("action", ""))
    if payload.get("ok") is not True:
        return f"日程操作失败：{payload.get('error') or '未知错误'}"

    if action == "list_events":
        events = payload.get("events") or []
        if not events:
            return "你目前没有未来日程。"
        return "未来日程：\n" + "\n".join(_event_line(event) for event in events)

    if action == "events_on_day":
        events = payload.get("events") or []
        if not events:
            return f"{payload.get('date')} 没有日程。"
        return f"{payload.get('date')} 的日程：\n" + "\n".join(_event_line(event) for event in events)

    if action == "free_time":
        blocks = payload.get("blocks") or []
        if not blocks:
            return f"{payload.get('date')} 没有符合条件的空闲时间。"
        return f"{payload.get('date')} 可用时间：\n" + "\n".join(_block_line(block) for block in blocks)

    if action == "add_event":
        if payload.get("added"):
            return "已添加日程：" + _event_line(payload.get("event") or {})
        conflicts = payload.get("conflicts") or []
        return "日程冲突，暂未添加：\n" + "\n".join(_event_line(event) for event in conflicts)

    if action == "schedule_event":
        if payload.get("scheduled"):
            return "已安排日程：" + _event_line(payload.get("event") or {})
        return f"{payload.get('date')} 没找到合适空档。"

    if action == "delete_event":
        return f"已删除事件 {payload.get('event_id')}。" if payload.get("deleted") else f"没有找到事件 {payload.get('event_id')}。"

    if action == "set_preference":
        return "已保存你的日程偏好。"

    if action == "get_preference":
        return f"你的日程偏好：{payload.get('preference') or '暂无'}"

    if action in {"move_event", "reschedule_event"}:
        if payload.get("updated"):
            return "已更新日程：" + _event_line(payload.get("event") or {})
        conflicts = payload.get("conflicts") or []
        if conflicts:
            return "更新后会冲突，暂未修改：\n" + "\n".join(_event_line(event) for event in conflicts)
        return "未能更新日程。"

    return f"日程操作完成：{action}"


def calendar_context_from_result(
    user_text: str,
    actions: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for result in results:
        event = result.get("event")
        if isinstance(event, dict):
            events.append(event)
        for item in result.get("events") or []:
            if isinstance(item, dict):
                events.append(item)
    return {
        "user_text": user_text,
        "actions": actions,
        "results": results,
        "events": events[-8:],
    }


def summarize_weather_results(
    results: list[dict[str, Any]],
    *,
    goal: str = "forecast",
    rain_threshold: int = 30,
) -> str:
    if not results:
        return "天气查询没有返回结果。"

    lines: list[str] = []
    for result in results:
        if result.get("ok") is not True:
            lines.append(f"天气查询失败：{result.get('error') or '未知错误'}")
            continue
        location = result.get("location") or {}
        location_name = location.get("name") if isinstance(location, dict) else ""
        title = f"{location_name or result.get('location_query') or '该地区'} {result.get('date')} 天气"
        periods = result.get("periods") or []
        if goal == "avoid_rain":
            good_periods = [
                period for period in periods
                if _period_rain_probability(period) is not None
                and _period_rain_probability(period) <= rain_threshold
            ]
            if good_periods:
                lines.append(
                    title
                    + f"\n降水概率不高于 {rain_threshold}% 的时段：\n"
                    + "\n".join(_weather_period_line(period) for period in good_periods)
                )
            else:
                lines.append(
                    title
                    + f"\n没有找到降水概率不高于 {rain_threshold}% 的时段。"
                )
        else:
            lines.append(
                title + "：\n" + "\n".join(_weather_period_line(period) for period in periods)
            )
    return "\n\n".join(lines)


def _validate_plan(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("ok") is not True:
        return {
            "ok": False,
            "error": str(data.get("error") or "我还不能确定你的日程意图。"),
            "ask_user": str(data.get("ask_user") or ""),
        }
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        return {"ok": False, "error": "没有解析出可执行的日程动作。", "ask_user": ""}
    normalized_actions = []
    for item in actions[:3]:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "")).strip().lower()
        if action not in _allowed_actions():
            continue
        normalized = dict(item)
        normalized["action"] = action
        normalized_actions.append(normalized)
    if not normalized_actions:
        return {"ok": False, "error": "没有解析出受支持的日程动作。", "ask_user": ""}
    return {
        "ok": True,
        "intent": "calendar",
        "summary": str(data.get("summary", "正在处理日程。")),
        "actions": normalized_actions,
    }


def _validate_weather_plan(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("ok") is not True:
        return {
            "ok": False,
            "error": str(data.get("error") or "我还不能确定天气查询信息。"),
            "ask_user": str(data.get("ask_user") or ""),
        }
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        return {"ok": False, "error": "没有解析出可执行的天气查询。", "ask_user": ""}
    normalized_actions = []
    for item in actions[:4]:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "hourly_forecast")).strip().lower()
        if action not in {"hourly_forecast", "forecast"}:
            continue
        location = str(item.get("location") or data.get("location") or "").strip()
        date_value = str(item.get("date") or "").strip()
        if not location or not _is_iso_date(date_value):
            continue
        normalized = dict(item)
        normalized["action"] = action
        normalized["location"] = location
        normalized.setdefault("country_code", "CN")
        normalized.setdefault("timezone", "Asia/Shanghai")
        normalized.setdefault("interval_hours", 3)
        normalized_actions.append(normalized)
    if not normalized_actions:
        return {"ok": False, "error": "天气查询缺少地点或日期。", "ask_user": "请告诉我地点和日期，比如：上海这周末。"}
    return {
        "ok": True,
        "intent": "weather",
        "summary": str(data.get("summary", "我先查询天气。")),
        "goal": str(data.get("goal", "forecast")),
        "schedule_requested": bool(data.get("schedule_requested", False)),
        "activity_title": str(data.get("activity_title") or "天气相关安排"),
        "duration_minutes": _positive_int(data.get("duration_minutes"), default=60),
        "location": str(data.get("location") or normalized_actions[0]["location"]),
        "actions": normalized_actions,
    }


def _allowed_actions() -> set[str]:
    return {
        "list_events",
        "events_on_day",
        "free_time",
        "add_event",
        "schedule_event",
        "delete_event",
        "set_preference",
        "get_preference",
        "move_event",
        "reschedule_event",
    }


def _event_line(event: dict[str, Any]) -> str:
    event_id = event.get("id", "?")
    title = event.get("title", "未命名")
    starts_at = _compact_datetime(str(event.get("starts_at", "")))
    ends_at = _compact_time(str(event.get("ends_at", "")))
    return f"{event_id}. {starts_at}-{ends_at} {title}"


def _block_line(block: dict[str, Any]) -> str:
    return f"{_compact_datetime(str(block.get('starts_at', '')))}-{_compact_time(str(block.get('ends_at', '')))}"


def _compact_datetime(value: str) -> str:
    if "T" not in value:
        return value
    day, time_part = value.split("T", 1)
    return f"{day} {time_part[:5]}"


def _compact_time(value: str) -> str:
    if "T" in value:
        return value.split("T", 1)[1][:5]
    return value[:5]


def _weekend_dates(today: date, *, weeks_ahead: int) -> list[date]:
    days_until_saturday = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_until_saturday + weeks_ahead * 7)
    return [saturday, saturday + timedelta(days=1)]


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _period_rain_probability(period: dict[str, Any]) -> int | None:
    value = period.get("max_precipitation_probability")
    if value is None:
        return None
    return int(value)


def _weather_period_line(period: dict[str, Any]) -> str:
    probability = period.get("max_precipitation_probability")
    probability_text = "未知" if probability is None else f"{probability}%"
    return (
        f"{_compact_datetime(str(period.get('starts_at', '')))}-"
        f"{_compact_time(str(period.get('ends_at', '')))} "
        f"{period.get('weather') or '未知'}，降水概率最高 {probability_text}"
    )


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
