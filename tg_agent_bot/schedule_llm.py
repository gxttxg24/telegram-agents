from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .llm import OllamaClient
from .schedule import LOCAL_TZ, ParsedEvent, ScheduleParseError, ScheduleRequest


SYSTEM_PROMPT = """
你是日程 JSON 抽取器，只返回一个 JSON 对象，不要解释。
固定使用东八区 UTC+08:00。start_at/end_at 必须带 +08:00。

返回格式：
成功：{"ok":true,"title":"事件名","start_at":"YYYY-MM-DDTHH:MM:SS+08:00","end_at":"YYYY-MM-DDTHH:MM:SS+08:00"}
失败：{"ok":false,"error":"简短中文原因"}

规则：
1. 今天/明天/后天/大后天/下周几都按“当前东八区时间”解析。
2. 输出 24 小时制。下午/晚上/今晚/傍晚会把 1-11 点理解为 13-23 点；“晚上五点/傍晚五点”按 17:00。
3. 上午/早上按 01:00-11:00；中午12点是 12:00；凌晨是 00:00-05:00。
4. “半”是 30 分钟，例如三点半。大概/左右/差不多/约 不影响提取。
5. “从A到B”“A到B”“A-B”“A开始B结束”都是时间范围。
6. 前面的“下午/晚上/上午”等可以修饰后面整段时间，即使中间隔着活动名，例如“明天晚上打球，从五点到七点”=17:00-19:00。
7. 没有结束时间则默认 1 小时。没有日期或无法判断上午/下午时返回 ok=false。
8. title 去掉日期、时间、从/到/开始/结束/大概等词，只保留活动名。

明天五点到七点打球 => {"ok":false,"error":"请说明是上午五点还是下午五点。"}
""".strip()

DAY_SYSTEM_PROMPT = """
你是日期 JSON 抽取器，只返回一个 JSON 对象，不要解释。
固定使用东八区 UTC+08:00，只根据用户提示中的“当前东八区时间”和日期表解析。

返回格式：
成功：{"ok":true,"date":"YYYY-MM-DD"}
失败：{"ok":false,"error":"简短中文原因"}

规则：
1. 今天/明天/后天/大后天直接使用用户提示中给出的日期表。
2. 周几/星期几/礼拜几按当前东八区日期向后解析；“下周几”解析到下一周。
3. 用户问空闲时间时，只需要抽取日期，不要输出 start_at/end_at。
4. 如果用户没有提供日期，也没有今天/明天等相对日期，返回 ok=false。
""".strip()

PLAN_SYSTEM_PROMPT = """
你是日程安排请求 JSON 抽取器，只返回一个 JSON 对象，不要解释。
固定使用东八区 UTC+08:00。

返回格式：
成功：{"ok":true,"title":"活动名","date":"YYYY-MM-DD","duration_minutes":120,"kind":"default"}
失败：{"ok":false,"error":"简短中文原因"}

规则：
1. 今天/明天/后天/大后天直接使用用户提示中的日期表。
2. title 是要安排的活动，例如“打球”“约朋友吃饭”“看电影”。
3. duration_minutes 是持续时间。2小时=120，半小时=30，90分钟=90。
4. 如果用户没有说时长：吃饭默认 90 分钟，其它活动默认 60 分钟。
5. kind 只能是 default、meal、lunch、dinner。
6. “吃饭/约饭/聚餐/午饭/晚饭/晚餐/午餐”属于饭点活动。午饭/午餐 kind=lunch；晚饭/晚餐 kind=dinner；只说吃饭/约饭 kind=meal。
7. 饭点活动不能随便排到上午十点或下午三点。
8. 如果没有日期，返回 ok=false。
""".strip()

JSON_TIMEOUT_SECONDS = 30.0
MAX_EXTRACTION_ATTEMPTS = 2
GENERIC_EVENT_ERROR = "\u6211\u8fd8\u6ca1\u80fd\u7a33\u5b9a\u63d0\u53d6\u51fa\u4e8b\u4ef6\u65f6\u95f4\u548c\u6807\u9898\u3002\u8bf7\u6362\u4e00\u79cd\u66f4\u660e\u786e\u7684\u8bf4\u6cd5\uff0c\u6bd4\u5982\uff1a/add_event \u660e\u5929 14:00-15:30 \u7ec4\u4f1a\u3002"
GENERIC_DAY_ERROR = "\u6211\u8fd8\u6ca1\u80fd\u7a33\u5b9a\u63d0\u53d6\u51fa\u65e5\u671f\u3002\u8bf7\u6362\u4e00\u79cd\u66f4\u660e\u786e\u7684\u8bf4\u6cd5\uff0c\u6bd4\u5982\uff1a/free_time \u660e\u5929\u3002"


EVENT_USER_PROMPT = """
当前东八区时间：{now}
今天日期：{today}
明天日期：{tomorrow}
后天日期：{after_tomorrow}
大后天日期：{three_days_later}
固定时区：UTC+08:00 / Asia/Shanghai
任务：从下面的用户文本中抽取一个日程事件。

本次抽取必须遵守：
- 如果用户说“明天”，日期必须使用 {tomorrow}，不能使用 {today}。
- “晚上/今晚/傍晚 + 五点到七点/从五点到七点”必须是 17:00-19:00。
- 如果活动名夹在日期和时间中间，例如“明天晚上打球，从五点到七点”，标题是“打球”，时间是 {tomorrow} 17:00-19:00。

参考示例：
- 明天晚上打球，从五点到七点 => {{"ok":true,"title":"打球","start_at":"{tomorrow}T17:00:00+08:00","end_at":"{tomorrow}T19:00:00+08:00"}}
- 明天下午，大概两点开始组会，三点半结束 => {{"ok":true,"title":"组会","start_at":"{tomorrow}T14:00:00+08:00","end_at":"{tomorrow}T15:30:00+08:00"}}

成功时必须返回这个 JSON 结构：
{{
  "ok": true,
  "title": "去掉日期和时间后的事件标题",
  "start_at": "YYYY-MM-DDTHH:MM:SS+08:00",
  "end_at": "YYYY-MM-DDTHH:MM:SS+08:00"
}}

失败时必须返回这个 JSON 结构：
{{
  "ok": false,
  "error": "简短中文原因"
}}

用户文本：{text}
""".strip()


DAY_USER_PROMPT = """
当前东八区时间：{now}
今天日期：{today}
明天日期：{tomorrow}
后天日期：{after_tomorrow}
大后天日期：{three_days_later}
固定时区：UTC+08:00 / Asia/Shanghai
任务：从下面的用户文本中抽取要查询空闲时间的目标日期。

成功时必须返回这个 JSON 结构：
{{
  "ok": true,
  "date": "YYYY-MM-DD"
}}

失败时必须返回这个 JSON 结构：
{{
  "ok": false,
  "error": "简短中文原因"
}}

用户文本：{text}
""".strip()


PLAN_USER_PROMPT = """
当前东八区时间：{now}
今天日期：{today}
明天日期：{tomorrow}
后天日期：{after_tomorrow}
大后天日期：{three_days_later}
固定时区：UTC+08:00 / Asia/Shanghai
任务：从用户文本中抽取“要安排的活动、日期、时长、活动类型”。
请只返回 JSON 对象，不要返回解释。

示例：
- 明天找时间打球2个小时 => {{"ok":true,"title":"打球","date":"{tomorrow}","duration_minutes":120,"kind":"default"}}
- 明天约朋友吃饭 => {{"ok":true,"title":"约朋友吃饭","date":"{tomorrow}","duration_minutes":90,"kind":"meal"}}
- 明天中午约饭 => {{"ok":true,"title":"约饭","date":"{tomorrow}","duration_minutes":90,"kind":"lunch"}}
- 明天晚上吃饭 => {{"ok":true,"title":"吃饭","date":"{tomorrow}","duration_minutes":90,"kind":"dinner"}}

用户文本：{text}
""".strip()


async def parse_event_with_llm(
    llm: OllamaClient,
    text: str,
    *,
    now: datetime | None = None,
) -> ParsedEvent:
    base_now = now or datetime.now(LOCAL_TZ)
    dates = _relative_dates(base_now)
    user_prompt = EVENT_USER_PROMPT.format(
        now=base_now.isoformat(),
        text=text,
        **dates,
    )
    last_error: Exception | None = None
    for _ in range(MAX_EXTRACTION_ATTEMPTS):
        try:
            data = await llm.json_reply(
                DAY_SYSTEM_PROMPT,
                user_prompt,
                timeout_seconds=JSON_TIMEOUT_SECONDS,
            )
            return _event_from_json(data)
        except Exception as exc:
            last_error = exc
    raise _final_parse_error(last_error, GENERIC_EVENT_ERROR)


async def parse_day_with_llm(
    llm: OllamaClient,
    text: str,
    *,
    now: datetime | None = None,
) -> date:
    base_now = now or datetime.now(LOCAL_TZ)
    dates = _relative_dates(base_now)
    user_prompt = DAY_USER_PROMPT.format(
        now=base_now.isoformat(),
        text=text,
        **dates,
    )
    last_error: Exception | None = None
    for _ in range(MAX_EXTRACTION_ATTEMPTS):
        try:
            data = await llm.json_reply(
                SYSTEM_PROMPT,
                user_prompt,
                timeout_seconds=JSON_TIMEOUT_SECONDS,
            )
            return _day_from_json(data)
        except Exception as exc:
            last_error = exc
    raise _final_parse_error(last_error, GENERIC_DAY_ERROR)


async def parse_schedule_request_with_llm(
    llm: OllamaClient,
    text: str,
    *,
    now: datetime | None = None,
) -> ScheduleRequest:
    base_now = now or datetime.now(LOCAL_TZ)
    dates = _relative_dates(base_now)
    user_prompt = PLAN_USER_PROMPT.format(
        now=base_now.isoformat(),
        text=text,
        **dates,
    )
    last_error: Exception | None = None
    for _ in range(MAX_EXTRACTION_ATTEMPTS):
        try:
            data = await llm.json_reply(
                PLAN_SYSTEM_PROMPT,
                user_prompt,
                timeout_seconds=JSON_TIMEOUT_SECONDS,
            )
            return _schedule_request_from_json(data)
        except Exception as exc:
            last_error = exc
    raise _final_parse_error(
        last_error,
        "\u6211\u8fd8\u6ca1\u80fd\u7a33\u5b9a\u63d0\u53d6\u51fa\u8981\u5b89\u6392\u7684\u6d3b\u52a8\u3001\u65e5\u671f\u548c\u65f6\u957f\u3002\u8bf7\u6362\u4e00\u79cd\u66f4\u660e\u786e\u7684\u8bf4\u6cd5\uff0c\u6bd4\u5982\uff1a/schedule_event \u660e\u5929\u627e\u65f6\u95f4\u6253\u74032\u4e2a\u5c0f\u65f6\u3002",
    )


def _event_from_json(data: dict[str, Any]) -> ParsedEvent:
    _raise_if_not_ok(data)
    title = _required_string(data, "title").strip()
    start_at = _parse_datetime(_required_string(data, "start_at"), "start_at")
    end_at = _parse_datetime(_required_string(data, "end_at"), "end_at")
    if not title:
        title = "\u672a\u547d\u540d\u4e8b\u4ef6"
    if end_at <= start_at:
        raise ScheduleParseError("\u7ed3\u675f\u65f6\u95f4\u5fc5\u987b\u665a\u4e8e\u5f00\u59cb\u65f6\u95f4\u3002")
    return ParsedEvent(title=title, starts_at=start_at, ends_at=end_at)


def _day_from_json(data: dict[str, Any]) -> date:
    _raise_if_not_ok(data)
    value = _required_string(data, "date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ScheduleParseError("\u5927\u6a21\u578b\u8fd4\u56de\u7684\u65e5\u671f\u683c\u5f0f\u4e0d\u6b63\u786e\u3002") from exc


def _schedule_request_from_json(data: dict[str, Any]) -> ScheduleRequest:
    _raise_if_not_ok(data)
    title = _required_string(data, "title")
    target_day = _date_from_json_value(_required_string(data, "date"))
    duration = data.get("duration_minutes")
    if not isinstance(duration, int):
        raise ScheduleParseError("LLM JSON field duration_minutes must be an integer.")
    if duration <= 0 or duration > 12 * 60:
        raise ScheduleParseError("\u6d3b\u52a8\u65f6\u957f\u4e0d\u592a\u5408\u7406\uff0c\u8bf7\u6362\u4e00\u79cd\u8bf4\u6cd5\u3002")
    kind = data.get("kind", "default")
    if kind not in {"default", "meal", "lunch", "dinner"}:
        kind = "default"
    return ScheduleRequest(
        title=title,
        target_day=target_day,
        duration_minutes=duration,
        kind=kind,
    )


def _raise_if_not_ok(data: dict[str, Any]) -> None:
    if data.get("ok") is True:
        return
    error = data.get("error")
    if isinstance(error, str) and error.strip():
        raise ScheduleParseError(error.strip())
    raise ScheduleParseError("\u6211\u8fd8\u6ca1\u6709\u4ece\u8fd9\u53e5\u8bdd\u91cc\u63d0\u53d6\u51fa\u5b8c\u6574\u65f6\u95f4\u3002")


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScheduleParseError(f"LLM JSON missing required string field: {key}")
    return value.strip()


def _date_from_json_value(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ScheduleParseError("LLM JSON date field must be YYYY-MM-DD.") from exc


def _parse_datetime(value: str, key: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ScheduleParseError(f"LLM JSON field {key} must be ISO datetime.") from exc
    if parsed.tzinfo is None:
        raise ScheduleParseError(f"LLM JSON field {key} must include +08:00 timezone.")
    return parsed.astimezone(LOCAL_TZ)


def _final_parse_error(error: Exception | None, generic_message: str) -> ScheduleParseError:
    if isinstance(error, ScheduleParseError):
        return error
    return ScheduleParseError(generic_message)


def _relative_dates(now: datetime) -> dict[str, str]:
    today = now.date()
    return {
        "today": today.isoformat(),
        "tomorrow": date.fromordinal(today.toordinal() + 1).isoformat(),
        "after_tomorrow": date.fromordinal(today.toordinal() + 2).isoformat(),
        "three_days_later": date.fromordinal(today.toordinal() + 3).isoformat(),
    }
