from __future__ import annotations

import json
import logging
import re
import sys
from copy import deepcopy
from dataclasses import replace

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    PersistenceInput,
    filters,
)

from .b2b import (
    ACK,
    B2BProtocolError,
    make_ack,
    make_payload_request,
    make_request,
    make_response,
    normalize_username,
    parse_envelope,
    should_ack,
    username_matches,
)
from .bots.calendar import (
    CalendarServiceError,
    handle_calendar_request,
    is_calendar_request,
)
from .config import load_settings
from .llm import LLMClient, OllamaClient, OpenAIResponsesClient
from .memory import MemoryStore
from .bots.orchestrator import (
    calendar_context_from_result,
    parse_calendar_plan,
    parse_weather_plan,
    summarize_calendar_result,
    summarize_weather_results,
)
from .schedule import (
    ScheduleParseError,
    ScheduleStore,
    ParsedEvent,
    format_datetime_range,
    format_event,
    format_time_range,
    free_time_blocks,
    pick_schedule_slot,
)
from .schedule_llm import (
    parse_day_with_llm,
    parse_event_with_llm,
    parse_schedule_request_with_llm,
)
from .bots.slot_matcher import (
    SlotMatcherServiceError,
    handle_slot_matcher_request,
    is_slot_matcher_request,
)
from .bots.weather import (
    WeatherServiceError,
    handle_weather_request,
    is_weather_request,
)


logger = logging.getLogger(__name__)
PENDING_EVENT_KEY = "pending_event"
TELEGRAM_TEXT_LIMIT = 4096


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "你好，我已经在线。直接发私聊消息可以测试上下文记忆，也可以用 /add_event 添加日程。"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    memory: MemoryStore = context.application.bot_data["memory"]
    memory.clear(update.effective_chat.id)
    await update.effective_message.reply_text("已清空这段私聊的上下文记忆。")


async def add_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    schedule: ScheduleStore = context.application.bot_data["schedule"]
    llm: LLMClient = context.application.bot_data["extract_llm"]
    payload = _command_payload(update)
    try:
        parsed = await parse_event_with_llm(llm, payload)
    except ScheduleParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        logger.warning("LLM event extraction failed after retries: %s", exc)
        await update.effective_message.reply_text(
            "\u5927\u6a21\u578b\u63d0\u53d6\u65e5\u7a0b\u5931\u8d25\uff0c\u8fd9\u6b21\u6ca1\u6709\u6dfb\u52a0\u4e8b\u4ef6\u3002\u8bf7\u6362\u4e00\u79cd\u66f4\u660e\u786e\u7684\u8bf4\u6cd5\u91cd\u8bd5\u3002"
        )
        return

    conflicts = schedule.conflicting_events(update.effective_chat.id, parsed)
    if conflicts:
        context.chat_data[PENDING_EVENT_KEY] = {
            "event": parsed,
            "conflict_ids": [event.id for event in conflicts],
        }
        await update.effective_message.reply_text(
            "\u8fd9\u4e2a\u65e5\u7a0b\u548c\u5df2\u6709\u4e8b\u4ef6\u51b2\u7a81\uff0c\u6682\u65f6\u8fd8\u6ca1\u6709\u6dfb\u52a0\uff1a\n"
            f"\u5f85\u6dfb\u52a0\uff1a{format_datetime_range(parsed.starts_at, parsed.ends_at)} {parsed.title}\n"
            "\u51b2\u7a81\u4e8b\u4ef6\uff1a\n"
            + "\n".join(format_event(event) for event in conflicts)
            + "\n\n\u5982\u679c\u8981\u5220\u9664\u51b2\u7a81\u4e8b\u4ef6\u5e76\u52a0\u5165\u65b0\u4e8b\u4ef6\uff0c\u8bf7\u56de\u590d\u201c\u8986\u76d6\u201d\uff1b\u8981\u653e\u5f03\u8bf7\u56de\u590d\u201c\u53d6\u6d88\u201d\u3002"
        )
        return

    event = schedule.add_event(update.effective_chat.id, parsed)
    await update.effective_message.reply_text(
        f"已添加：{event.id}. {format_datetime_range(event.starts_at, event.ends_at)} {event.title}"
    )


async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    schedule: ScheduleStore = context.application.bot_data["schedule"]
    events = schedule.list_events(update.effective_chat.id)
    if not events:
        await update.effective_message.reply_text("还没有未来日程。")
        return

    await update.effective_message.reply_text(
        "未来日程：\n" + "\n".join(format_event(event) for event in events)
    )


async def free_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    schedule: ScheduleStore = context.application.bot_data["schedule"]
    llm: LLMClient = context.application.bot_data["extract_llm"]
    payload = _command_payload(update)
    try:
        target_day = await parse_day_with_llm(llm, payload)
    except ScheduleParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        logger.warning(
            "LLM day extraction failed after retries: %s: %s",
            type(exc).__name__,
            exc,
        )
        await update.effective_message.reply_text(
            "\u5927\u6a21\u578b\u63d0\u53d6\u65e5\u671f\u5931\u8d25\u3002\u8bf7\u6362\u4e00\u79cd\u66f4\u660e\u786e\u7684\u8bf4\u6cd5\u91cd\u8bd5\u3002"
        )
        return

    preference = schedule.get_preference(update.effective_chat.id)
    events = schedule.events_on_day(update.effective_chat.id, target_day)
    blocks = free_time_blocks(events, target_day, preference)
    if not blocks:
        await update.effective_message.reply_text(f"{target_day:%Y-%m-%d} 没有可推荐的空闲时间。")
        return

    preference_note = "\n已考虑你的偏好。" if preference else ""
    await update.effective_message.reply_text(
        f"{target_day:%Y-%m-%d} 可用时间：\n"
        + "\n".join(format_time_range(start, end) for start, end in blocks)
        + preference_note
    )


async def schedule_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    schedule: ScheduleStore = context.application.bot_data["schedule"]
    llm: LLMClient = context.application.bot_data["extract_llm"]
    payload = _command_payload(update)
    try:
        request = await parse_schedule_request_with_llm(llm, payload)
    except ScheduleParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception as exc:
        logger.warning(
            "LLM schedule request extraction failed after retries: %s: %s",
            type(exc).__name__,
            exc,
        )
        await update.effective_message.reply_text(
            "\u5927\u6a21\u578b\u63d0\u53d6\u5b89\u6392\u9700\u6c42\u5931\u8d25\u3002\u8bf7\u8bf4\u660e\u65e5\u671f\u3001\u6d3b\u52a8\u548c\u65f6\u957f\uff0c\u6bd4\u5982\uff1a/schedule_event \u660e\u5929\u627e\u65f6\u95f4\u6253\u74032\u4e2a\u5c0f\u65f6\u3002"
        )
        return

    events = schedule.events_on_day(update.effective_chat.id, request.target_day)
    preference = schedule.get_preference(update.effective_chat.id)
    slot = pick_schedule_slot(events, request, preference)
    if slot is None:
        await update.effective_message.reply_text(
            f"{request.target_day:%Y-%m-%d} \u6ca1\u6709\u627e\u5230\u9002\u5408\u5b89\u6392\u201c{request.title}\u201d\u7684\u7a7a\u6863\u3002"
        )
        return

    starts_at, ends_at = slot
    event = schedule.add_event(
        update.effective_chat.id,
        ParsedEvent(request.title, starts_at, ends_at),
    )
    await update.effective_message.reply_text(
        f"\u5df2\u5b89\u6392\uff1a{event.id}. {format_datetime_range(event.starts_at, event.ends_at)} {event.title}"
    )


async def delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    match = re.search(r"\d+", _command_payload(update))
    if match is None:
        await update.effective_message.reply_text("请提供事件编号，比如：/delete_event 3")
        return

    schedule: ScheduleStore = context.application.bot_data["schedule"]
    event_id = int(match.group())
    if schedule.delete_event(update.effective_chat.id, event_id):
        await update.effective_message.reply_text(f"已删除事件 {event_id}。")
    else:
        await update.effective_message.reply_text(f"没有找到事件 {event_id}。")


async def set_preference(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    preference = _command_payload(update)
    if not preference:
        await update.effective_message.reply_text(
            "请写下偏好，比如：/set_preference 我一般不想上午开会"
        )
        return

    schedule: ScheduleStore = context.application.bot_data["schedule"]
    schedule.set_preference(update.effective_chat.id, preference)
    await update.effective_message.reply_text("已保存你的会议偏好。")


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    schedule: ScheduleStore = context.application.bot_data["schedule"]
    preference = schedule.get_preference(update.effective_chat.id)
    if preference:
        await update.effective_message.reply_text(f"你的会议偏好：\n{preference}")
    else:
        await update.effective_message.reply_text("还没有保存会议偏好。")


async def b2b_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    payload = _command_payload(update)
    target_arg, _, text = payload.partition(" ")
    target_username = _resolve_b2b_target(context, target_arg)
    if target_username is None:
        await update.effective_message.reply_text(
            "用法：/b2b_ping @OtherBot 可选消息，或 /b2b_ping C 可选消息\n"
            + _format_b2b_peers(context)
        )
        return

    source = await _own_username(context)
    logger.info("Bot-to-bot ping requested from %s to %s", source, target_username)
    message = make_request(
        source=source,
        target=target_username,
        text=text.strip() or "hello from tg_agent_bot",
    )
    try:
        sent = await context.bot.send_message(
            chat_id=target_username,
            text=message.to_text(),
        )
    except Exception as exc:
        _remember_b2b_event(
            context,
            f"send failed request {message.id} to {target_username}: {type(exc).__name__}: {exc}",
        )
        logger.exception("Bot-to-bot REQUEST send failed")
        await update.effective_message.reply_text(
            f"发送失败：{type(exc).__name__}: {exc}\n"
            "请确认两个 bot 都在 BotFather 开启了 Bot-to-Bot Communication Mode。"
        )
        return

    _remember_b2b_event(
        context,
        f"sent request {message.id} to {target_username} telegram_message_id={sent.message_id}",
    )
    await update.effective_message.reply_text(
        f"已向 {target_username} 发送 bot-to-bot REQUEST：{message.id}"
    )


async def b2b_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    source = await _own_username(context)
    configured = context.application.bot_data.get("configured_bot_username") or "(not set)"
    seen_ids: set[str] = context.application.bot_data.setdefault("b2b_seen_ids", set())
    profile = context.application.bot_data.get("bot_profile") or "(default)"
    events = context.application.bot_data.setdefault("b2b_events", [])
    event_text = "\n".join(f"- {event}" for event in events[-8:]) or "- 暂无"
    await update.effective_message.reply_text(
        f"bot-to-bot 已启用。Profile：{profile}\n"
        f"本 bot：{source}\n"
        f".env username：{configured}\n"
        f"已见过结构化消息：{len(seen_ids)} 条\n"
        f"{_format_b2b_peers(context)}\n"
        "最近事件：\n"
        f"{event_text}\n"
        "发送测试：/b2b_ping C hello 或 /b2b_ping @OtherBot hello"
    )


async def b2b_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    payload = _command_payload(update)
    target_arg, _, json_text = payload.partition(" ")
    target_username = _resolve_b2b_target(context, target_arg)
    if target_username is None or not json_text.strip():
        await update.effective_message.reply_text(
            "用法：/b2b_calendar A {\"action\":\"free_time\",\"date\":\"2026-06-05\",\"min_duration_minutes\":120}\n"
            + _format_b2b_peers(context)
        )
        return

    try:
        calendar_payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        await update.effective_message.reply_text(f"JSON 无效：{exc}")
        return

    if not isinstance(calendar_payload, dict):
        await update.effective_message.reply_text("calendar payload 必须是 JSON object。")
        return

    calendar_payload.setdefault("service", "calendar")
    calendar_payload.setdefault("owner_chat_id", update.effective_chat.id)

    source = await _own_username(context)
    message = make_payload_request(
        source=source,
        target=target_username,
        payload=calendar_payload,
    )
    try:
        sent = await context.bot.send_message(chat_id=target_username, text=message.to_text())
    except Exception as exc:
        _remember_b2b_event(
            context,
            f"calendar send failed {message.id} to {target_username}: {type(exc).__name__}: {exc}",
        )
        logger.exception("Bot-to-bot calendar request send failed")
        await update.effective_message.reply_text(f"发送失败：{type(exc).__name__}: {exc}")
        return

    _remember_b2b_event(
        context,
        f"sent calendar {calendar_payload.get('action')} request {message.id} to {target_username} telegram_message_id={sent.message_id}",
    )
    await update.effective_message.reply_text(
        f"已向 {target_username} 发送 calendar.{calendar_payload.get('action')} 请求：{message.id}"
    )


async def b2b_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    payload = _command_payload(update)
    target_arg, _, json_text = payload.partition(" ")
    target_username = _resolve_b2b_target(context, target_arg)
    if target_username is None or not json_text.strip():
        await update.effective_message.reply_text(
            "用法：/b2b_weather B {\"location\":\"北京\",\"date\":\"2026-06-05\"}\n"
            + _format_b2b_peers(context)
        )
        return

    try:
        weather_payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        await update.effective_message.reply_text(f"JSON 无效：{exc}")
        return

    if not isinstance(weather_payload, dict):
        await update.effective_message.reply_text("weather payload 必须是 JSON object。")
        return

    weather_payload.setdefault("service", "weather")
    weather_payload.setdefault("action", "hourly_forecast")

    source = await _own_username(context)
    message = make_payload_request(
        source=source,
        target=target_username,
        payload=weather_payload,
    )
    try:
        sent = await context.bot.send_message(chat_id=target_username, text=message.to_text())
    except Exception as exc:
        _remember_b2b_event(
            context,
            f"weather send failed {message.id} to {target_username}: {type(exc).__name__}: {exc}",
        )
        logger.exception("Bot-to-bot weather request send failed")
        await update.effective_message.reply_text(f"发送失败：{type(exc).__name__}: {exc}")
        return

    _remember_b2b_event(
        context,
        f"sent weather {weather_payload.get('action')} request {message.id} to {target_username} telegram_message_id={sent.message_id}",
    )
    await update.effective_message.reply_text(
        f"已向 {target_username} 发送 weather.{weather_payload.get('action')} 请求：{message.id}"
    )


async def b2b_debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    me = await context.bot.get_me()
    source = await _own_username(context)
    configured = context.application.bot_data.get("configured_bot_username") or "(not set)"
    profile = context.application.bot_data.get("bot_profile") or "(default)"
    settings_summary = context.application.bot_data.get("settings_summary", {})
    peers = _format_b2b_peers(context)
    chat = update.effective_chat
    chat_label = f"{chat.type}:{chat.id}" if chat is not None else "(unknown)"
    await update.effective_message.reply_text(
        "b2b debug\n"
        f"profile: {profile}\n"
        f"getMe: id={me.id}, username=@{me.username}\n"
        f"protocol source: {source}\n"
        f".env username: {configured}\n"
        f"{peers}\n"
        f"chat: {chat_label}\n"
        f"persistence: {settings_summary.get('persistence', '')}\n"
        f"memory_db: {settings_summary.get('memory_db', '')}\n"
        f"schedule_db: {settings_summary.get('schedule_db', '')}"
    )


async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    user_text = update.effective_message.text or ""
    if not user_text.strip():
        return

    if await _handle_b2b_message(update, context, user_text):
        return

    if await _handle_pending_event_confirmation(update, context, user_text):
        return

    if _is_orchestrator_bot(context):
        if await _handle_orchestrator_text(update, context, user_text):
            return

    memory: MemoryStore = context.application.bot_data["memory"]
    llm: LLMClient = context.application.bot_data["llm"]
    history_turns: int = context.application.bot_data["history_turns"]
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    history = memory.recent(chat_id, limit=history_turns * 2)

    try:
        reply = await llm.reply(history=history, user_text=user_text)
    except Exception:
        logger.exception("LLM request failed")
        reply = (
            "我收到了你的消息，但本地开源模型暂时不可用。"
            "请确认 Ollama 已启动，并已拉取配置的模型。"
        )

    memory.add(chat_id, "user", user_text)
    memory.add(chat_id, "assistant", reply)
    await update.effective_message.reply_text(reply)


async def _handle_b2b_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
) -> bool:
    if update.effective_message is None:
        return False

    try:
        envelope = parse_envelope(user_text)
    except B2BProtocolError as exc:
        await update.effective_message.reply_text(f"收到 bot-to-bot 消息，但协议校验失败：{exc}")
        return True

    if envelope is None:
        return False

    my_username = await _own_username(context)
    seen_ids: set[str] = context.application.bot_data.setdefault("b2b_seen_ids", set())
    already_seen = envelope.id in seen_ids
    seen_ids.add(envelope.id)

    if already_seen:
        _remember_b2b_event(context, f"ignored duplicate {envelope.message_type} {envelope.id}")
        logger.info("Duplicate bot-to-bot message ignored: %s", envelope.id)
        return True

    if not envelope.target or not normalize_username(envelope.target):
        _remember_b2b_event(context, f"ignored message {envelope.id}: empty target")
        logger.info("Bot-to-bot message without target ignored: %s", envelope.id)
        return True

    if not username_matches(envelope.target, my_username):
        _remember_b2b_event(
            context,
            f"ignored {envelope.message_type} {envelope.id}: target {envelope.target}, this bot {my_username}",
        )
        logger.info(
            "Bot-to-bot message %s ignored because target is %s, this bot is %s",
            envelope.id,
            envelope.target,
            my_username,
        )
        return True

    sender = update.effective_user
    if sender is not None and sender.username:
        sender_username = normalize_username(sender.username)
        if not username_matches(sender_username, envelope.source):
            _remember_b2b_event(
                context,
                f"ignored {envelope.message_type} {envelope.id}: sender {sender_username}, source {envelope.source}",
            )
            logger.info(
                "Bot-to-bot message %s ignored because sender %s does not match source %s",
                envelope.id,
                sender_username,
                envelope.source,
            )
            return True

    if envelope.message_type == ACK:
        payload_kind = str(envelope.payload.get("kind", "")).strip().lower()
        if await _handle_orchestrator_b2b_result(context, envelope):
            return True
        if payload_kind == "calendar.result":
            _remember_b2b_event(
                context,
                f"received calendar.result {envelope.payload.get('action')} ok={envelope.payload.get('ok')} from {envelope.source}",
            )
        elif payload_kind == "weather.result":
            _remember_b2b_event(
                context,
                f"received weather.result {envelope.payload.get('action')} ok={envelope.payload.get('ok')} from {envelope.source}",
            )
        elif payload_kind == "slot_matcher.result":
            _remember_b2b_event(
                context,
                f"received slot_matcher.result ok={envelope.payload.get('ok')} from {envelope.source}",
            )
        else:
            _remember_b2b_event(
                context,
                f"received ack {envelope.id} from {envelope.source} for {envelope.correlation_id}",
            )
        _remember_b2b_event(
            context,
            f"payload={json.dumps(envelope.payload, ensure_ascii=False)[:800]}",
        )
        logger.info(
            "Bot-to-bot ACK received from %s for %s",
            envelope.source,
            envelope.correlation_id,
        )
        return True

    if is_calendar_request(envelope.payload):
        await _handle_calendar_b2b_request(context, envelope, my_username)
        return True

    if is_weather_request(envelope.payload):
        await _handle_weather_b2b_request(context, envelope, my_username)
        return True

    if is_slot_matcher_request(envelope.payload):
        await _handle_slot_matcher_b2b_request(context, envelope, my_username)
        return True

    if should_ack(envelope, seen_ids - {envelope.id}, my_username):
        ack = make_ack(source=my_username, request=envelope)
        seen_ids.add(ack.id)
        await context.bot.send_message(chat_id=envelope.source, text=ack.to_text())
        _remember_b2b_event(
            context,
            f"received request {envelope.id} from {envelope.source}; sent ack {ack.id}",
        )
        logger.info("Bot-to-bot ACK sent to %s for %s", envelope.source, envelope.id)
        return True

    _remember_b2b_event(
        context,
        f"consumed request {envelope.id} from {envelope.source} without ack depth={envelope.depth}/{envelope.max_depth}",
    )
    logger.info(
        "Bot-to-bot REQUEST %s consumed without ACK at depth %s/%s",
        envelope.id,
        envelope.depth,
        envelope.max_depth,
    )
    return True


async def _handle_calendar_b2b_request(
    context: ContextTypes.DEFAULT_TYPE,
    envelope,
    my_username: str,
) -> None:
    schedule: ScheduleStore = context.application.bot_data["schedule"]
    seen_ids: set[str] = context.application.bot_data.setdefault("b2b_seen_ids", set())

    try:
        result_payload = handle_calendar_request(schedule, envelope.payload)
    except CalendarServiceError as exc:
        result_payload = {
            "kind": "calendar.result",
            "service": "calendar",
            "action": str(envelope.payload.get("action", "")),
            "ok": False,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Calendar service request failed")
        result_payload = {
            "kind": "calendar.result",
            "service": "calendar",
            "action": str(envelope.payload.get("action", "")),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    response = make_response(source=my_username, request=envelope, payload=result_payload)
    seen_ids.add(response.id)
    await context.bot.send_message(chat_id=envelope.source, text=_telegram_safe_envelope_text(response))
    status = "ok" if result_payload.get("ok") else "error"
    _remember_b2b_event(
        context,
        f"calendar {result_payload.get('action') or '(missing)'} {status} for {envelope.source}; response {response.id}",
    )


async def _handle_weather_b2b_request(
    context: ContextTypes.DEFAULT_TYPE,
    envelope,
    my_username: str,
) -> None:
    seen_ids: set[str] = context.application.bot_data.setdefault("b2b_seen_ids", set())

    try:
        result_payload = await handle_weather_request(envelope.payload)
    except WeatherServiceError as exc:
        result_payload = {
            "kind": "weather.result",
            "service": "weather",
            "action": str(envelope.payload.get("action", "")),
            "ok": False,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Weather service request failed")
        result_payload = {
            "kind": "weather.result",
            "service": "weather",
            "action": str(envelope.payload.get("action", "")),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    response = make_response(source=my_username, request=envelope, payload=result_payload)
    seen_ids.add(response.id)
    await context.bot.send_message(chat_id=envelope.source, text=_telegram_safe_envelope_text(response))
    status = "ok" if result_payload.get("ok") else "error"
    _remember_b2b_event(
        context,
        f"weather {result_payload.get('action') or '(missing)'} {status} for {envelope.source}; response {response.id}",
    )


async def _handle_slot_matcher_b2b_request(
    context: ContextTypes.DEFAULT_TYPE,
    envelope,
    my_username: str,
) -> None:
    seen_ids: set[str] = context.application.bot_data.setdefault("b2b_seen_ids", set())

    try:
        result_payload = handle_slot_matcher_request(envelope.payload)
    except SlotMatcherServiceError as exc:
        result_payload = {
            "kind": "slot_matcher.result",
            "service": "slot_matcher",
            "action": str(envelope.payload.get("action", "")),
            "ok": False,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Slot matcher service request failed")
        result_payload = {
            "kind": "slot_matcher.result",
            "service": "slot_matcher",
            "action": str(envelope.payload.get("action", "")),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    response = make_response(source=my_username, request=envelope, payload=result_payload)
    seen_ids.add(response.id)
    await context.bot.send_message(chat_id=envelope.source, text=_telegram_safe_envelope_text(response))
    status = "ok" if result_payload.get("ok") else "error"
    _remember_b2b_event(
        context,
        f"slot_matcher {status} for {envelope.source}; response {response.id}",
    )


async def _handle_pending_event_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
) -> bool:
    if update.effective_chat is None or update.effective_message is None:
        return False

    pending = context.chat_data.get(PENDING_EVENT_KEY)
    if pending is None:
        return False

    normalized = user_text.strip().lower()
    overwrite_words = {"\u8986\u76d6", "\u66ff\u6362", "\u8986\u76d6\u65e7\u7684", "overwrite", "replace"}
    cancel_words = {"\u53d6\u6d88", "\u7b97\u4e86", "\u4e0d\u8981", "\u5426", "no", "n"}

    if normalized in overwrite_words:
        schedule: ScheduleStore = context.application.bot_data["schedule"]
        if isinstance(pending, dict):
            pending_event = pending["event"]
            conflict_ids = [int(event_id) for event_id in pending.get("conflict_ids", [])]
        else:
            pending_event = pending
            conflict_ids = []
        event = schedule.replace_events(update.effective_chat.id, conflict_ids, pending_event)
        context.chat_data.pop(PENDING_EVENT_KEY, None)
        await update.effective_message.reply_text(
            f"\u5df2\u8986\u76d6\u51b2\u7a81\u4e8b\u4ef6\u5e76\u6dfb\u52a0\uff1a{event.id}. {format_datetime_range(event.starts_at, event.ends_at)} {event.title}"
        )
        return True

    if normalized in cancel_words:
        context.chat_data.pop(PENDING_EVENT_KEY, None)
        await update.effective_message.reply_text("\u5df2\u53d6\u6d88\u6dfb\u52a0\u8fd9\u4e2a\u51b2\u7a81\u65e5\u7a0b\u3002")
        return True

    await update.effective_message.reply_text(
        "\u8fd8\u6709\u4e00\u4e2a\u51b2\u7a81\u65e5\u7a0b\u7b49\u5f85\u5904\u7406\u3002\u8bf7\u56de\u590d\u201c\u8986\u76d6\u201d\u5220\u9664\u51b2\u7a81\u4e8b\u4ef6\u5e76\u6dfb\u52a0\u65b0\u4e8b\u4ef6\uff0c\u6216\u56de\u590d\u201c\u53d6\u6d88\u201d\u653e\u5f03\u3002"
    )
    return True


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Telegram update failed", exc_info=context.error)


def build_application(profile: str | None = None) -> Application:
    settings = load_settings(profile)
    persistence = PicklePersistence(
        filepath=settings.telegram_persistence_file,
        store_data=PersistenceInput(bot_data=False),
    )
    memory = MemoryStore(settings.memory_db)
    schedule = ScheduleStore(settings.schedule_db)
    llm, extract_llm = _build_llm_clients(settings)

    application = (
        ApplicationBuilder()
        .token(settings.telegram_token)
        .persistence(persistence)
        .concurrent_updates(False)
        .build()
    )

    application.bot_data["memory"] = memory
    application.bot_data["schedule"] = schedule
    application.bot_data["llm"] = llm
    application.bot_data["extract_llm"] = extract_llm
    application.bot_data["history_turns"] = settings.history_turns
    application.bot_data["b2b_seen_ids"] = set()
    application.bot_data["b2b_events"] = []
    application.bot_data["bot_profile"] = settings.bot_profile
    application.bot_data["orchestrator_profile"] = settings.orchestrator_profile
    application.bot_data["calendar_bot_profile"] = settings.calendar_bot_profile
    application.bot_data["weather_bot_profile"] = settings.weather_bot_profile
    application.bot_data["slot_matcher_bot_profile"] = settings.slot_matcher_bot_profile
    application.bot_data["orchestrator_pending"] = {}
    application.bot_data["orchestrator_pending_slots"] = {}
    application.bot_data["orchestrator_context_by_chat"] = {}
    application.bot_data["configured_bot_username"] = normalize_username(settings.telegram_username)
    application.bot_data["bot_peers"] = {
        profile: normalize_username(username)
        for profile, username in settings.bot_peers.items()
    }
    application.bot_data["settings_summary"] = {
        "persistence": str(settings.telegram_persistence_file),
        "memory_db": str(settings.memory_db),
        "schedule_db": str(settings.schedule_db),
    }

    private_chat = filters.ChatType.PRIVATE
    application.add_handler(CommandHandler("start", start, filters=private_chat))
    application.add_handler(CommandHandler("reset", reset, filters=private_chat))
    application.add_handler(CommandHandler("add_event", add_event, filters=private_chat))
    application.add_handler(CommandHandler("list_events", list_events, filters=private_chat))
    application.add_handler(CommandHandler("free_time", free_time, filters=private_chat))
    application.add_handler(CommandHandler("schedule_event", schedule_event, filters=private_chat))
    application.add_handler(CommandHandler("delete_event", delete_event, filters=private_chat))
    application.add_handler(CommandHandler("set_preference", set_preference, filters=private_chat))
    application.add_handler(CommandHandler("show_profile", show_profile, filters=private_chat))
    application.add_handler(CommandHandler("b2b_ping", b2b_ping))
    application.add_handler(CommandHandler("b2b_status", b2b_status))
    application.add_handler(CommandHandler("b2b_calendar", b2b_calendar))
    application.add_handler(CommandHandler("b2b_weather", b2b_weather))
    application.add_handler(CommandHandler("b2b_debug", b2b_debug))
    application.add_handler(
        MessageHandler(
            private_chat & filters.TEXT & ~filters.COMMAND,
            handle_private_text,
        )
    )
    application.add_error_handler(error_handler)
    return application


def main(profile: str | None = None) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    application = build_application(profile or _profile_from_argv(sys.argv[1:]))
    profile_name = application.bot_data.get("bot_profile", "")
    settings_summary = application.bot_data.get("settings_summary", {})
    logger.info(
        "Telegram agent bot%s is starting with long polling.",
        f" profile {profile_name}" if profile_name else "",
    )
    logger.info(
        "Bot storage: persistence=%s memory=%s schedule=%s",
        settings_summary.get("persistence", ""),
        settings_summary.get("memory_db", ""),
        settings_summary.get("schedule_db", ""),
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def _command_payload(update: Update) -> str:
    if update.effective_message is None or update.effective_message.text is None:
        return ""
    return update.effective_message.text.partition(" ")[2].strip()


def _remember_b2b_event(context: ContextTypes.DEFAULT_TYPE, event: str) -> None:
    events = context.application.bot_data.setdefault("b2b_events", [])
    events.append(event)
    del events[:-20]


async def _handle_orchestrator_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
) -> bool:
    if update.effective_chat is None or update.effective_message is None:
        return False

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    extract_llm: LLMClient = context.application.bot_data["extract_llm"]
    context_by_chat: dict[int, list[dict]] = context.application.bot_data.setdefault(
        "orchestrator_context_by_chat",
        {},
    )
    chat_id = update.effective_chat.id
    recent_context = context_by_chat.setdefault(chat_id, [])
    pending_slots: dict[int, dict] = context.application.bot_data.setdefault(
        "orchestrator_pending_slots",
        {},
    )
    pending = pending_slots.get(chat_id)

    if pending and pending.get("service") == "weather":
        combined_text = (
            f"{pending.get('original_text', '')}\n"
            f"用户补充信息：{user_text}"
        )
        try:
            plan = await parse_weather_plan(extract_llm, combined_text)
        except Exception:
            logger.exception("Orchestrator pending weather planning failed")
            await update.effective_message.reply_text(
                "我还是没能补全这次天气查询。请直接说完整一点，比如：上海这周末找不下雨的时间。"
            )
            return True

        if plan.get("ok") is True:
            pending_slots.pop(chat_id, None)
            await _start_orchestrator_weather_workflow(
                update,
                context,
                user_text=str(pending.get("original_text", user_text)),
                plan=plan,
            )
            return True

        pending["last_user_text"] = user_text
        ask_user = str(plan.get("ask_user") or plan.get("error") or "还缺少地点或日期。")
        await update.effective_message.reply_text(ask_user)
        return True

    if _looks_like_weather_request(user_text):
        try:
            plan = await parse_weather_plan(extract_llm, user_text)
        except Exception:
            logger.exception("Orchestrator weather planning failed")
            await update.effective_message.reply_text(
                "我还没能把这句话稳定解析成天气查询。请说明地点和日期，比如：上海这周末会不会下雨。"
            )
            return True

        if plan.get("ok") is not True:
            ask_user = str(plan.get("ask_user") or plan.get("error") or "请告诉我地点和日期。")
            pending_slots[chat_id] = {
                "service": "weather",
                "original_text": user_text,
                "ask_user": ask_user,
            }
            await update.effective_message.reply_text(ask_user)
            return True

        await _start_orchestrator_weather_workflow(
            update,
            context,
            user_text=user_text,
            plan=plan,
        )
        return True

    try:
        plan = await parse_calendar_plan(
            extract_llm,
            user_text,
            context=recent_context,
        )
    except Exception as exc:
        logger.exception("Orchestrator calendar planning failed")
        await update.effective_message.reply_text(
            "我还没能把这句话稳定解析成日程操作。请换一种更明确的说法，比如：明天两点到三点组会。"
        )
        return True

    if plan.get("ok") is not True:
        ask_user = str(plan.get("ask_user") or plan.get("error") or "请补充一下日程信息。")
        await update.effective_message.reply_text(ask_user)
        return True

    actions = plan["actions"]
    workflow = {
        "user_chat_id": chat_id,
        "user_text": user_text,
        "actions": actions,
        "index": 0,
        "results": [],
    }

    try:
        await _send_orchestrator_calendar_action(context, workflow)
    except Exception as exc:
        logger.exception("Failed to send orchestrator calendar action")
        await update.effective_message.reply_text(f"我解析到了日程操作，但发送给 CalendarBot 失败：{exc}")
        return True

    await update.effective_message.reply_text(str(plan.get("summary") or "收到，我正在处理日程。"))
    return True


async def _start_orchestrator_weather_workflow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_text: str,
    plan: dict,
) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    workflow = {
        "service": "weather_schedule" if plan.get("schedule_requested") else "weather",
        "stage": "weather",
        "user_chat_id": update.effective_chat.id,
        "user_text": user_text,
        "goal": str(plan.get("goal", "forecast")),
        "activity_title": str(plan.get("activity_title") or "天气相关安排"),
        "duration_minutes": int(plan.get("duration_minutes") or 60),
        "rain_threshold": 30,
        "actions": plan["actions"],
        "index": 0,
        "results": [],
        "weather_results": [],
        "calendar_results": [],
    }
    try:
        await _send_orchestrator_weather_action(context, workflow)
    except Exception as exc:
        logger.exception("Failed to send orchestrator weather action")
        await update.effective_message.reply_text(f"我解析到了天气查询，但发送给 WeatherBot 失败：{exc}")
        return

    await update.effective_message.reply_text(str(plan.get("summary") or "我先查询天气。"))


async def _send_orchestrator_calendar_action(
    context: ContextTypes.DEFAULT_TYPE,
    workflow: dict,
) -> None:
    actions = workflow["actions"]
    index = int(workflow["index"])
    action_payload = dict(actions[index])
    action_payload["service"] = "calendar"
    action_payload["owner_chat_id"] = int(workflow["user_chat_id"])

    calendar_profile = str(context.application.bot_data.get("calendar_bot_profile") or "A")
    target_username = _resolve_b2b_target(context, calendar_profile)
    if target_username is None:
        raise RuntimeError(f"CalendarBot profile {calendar_profile} is not configured.")

    source = await _own_username(context)
    message = make_payload_request(
        source=source,
        target=target_username,
        payload=action_payload,
    )
    sent = await context.bot.send_message(chat_id=target_username, text=message.to_text())
    pending: dict[str, dict] = context.application.bot_data.setdefault(
        "orchestrator_pending",
        {},
    )
    pending[message.id] = workflow
    _remember_b2b_event(
        context,
        f"orchestrator sent calendar {action_payload.get('action')} request {message.id} to {target_username} telegram_message_id={sent.message_id}",
    )


async def _send_orchestrator_weather_action(
    context: ContextTypes.DEFAULT_TYPE,
    workflow: dict,
) -> None:
    actions = workflow["actions"]
    index = int(workflow["index"])
    action_payload = dict(actions[index])
    action_payload["service"] = "weather"

    weather_profile = str(context.application.bot_data.get("weather_bot_profile") or "B")
    target_username = _resolve_b2b_target(context, weather_profile)
    if target_username is None:
        raise RuntimeError(f"WeatherBot profile {weather_profile} is not configured.")

    source = await _own_username(context)
    message = make_payload_request(
        source=source,
        target=target_username,
        payload=action_payload,
    )
    sent = await context.bot.send_message(chat_id=target_username, text=message.to_text())
    pending: dict[str, dict] = context.application.bot_data.setdefault(
        "orchestrator_pending",
        {},
    )
    pending[message.id] = workflow
    _remember_b2b_event(
        context,
        f"orchestrator sent weather {action_payload.get('date')} request {message.id} to {target_username} telegram_message_id={sent.message_id}",
    )


async def _send_orchestrator_slot_matcher_action(
    context: ContextTypes.DEFAULT_TYPE,
    workflow: dict,
) -> None:
    actions = workflow["actions"]
    index = int(workflow["index"])
    action_payload = dict(actions[index])
    action_payload["service"] = "slot_matcher"

    matcher_profile = str(context.application.bot_data.get("slot_matcher_bot_profile") or "D")
    target_username = _resolve_b2b_target(context, matcher_profile)
    if target_username is None:
        raise RuntimeError(f"SlotMatcherBot profile {matcher_profile} is not configured.")

    source = await _own_username(context)
    message = make_payload_request(
        source=source,
        target=target_username,
        payload=action_payload,
    )
    sent = await context.bot.send_message(chat_id=target_username, text=message.to_text())
    pending: dict[str, dict] = context.application.bot_data.setdefault(
        "orchestrator_pending",
        {},
    )
    pending[message.id] = workflow
    _remember_b2b_event(
        context,
        f"orchestrator sent slot_matcher request {message.id} to {target_username} telegram_message_id={sent.message_id}",
    )


async def _handle_orchestrator_b2b_result(
    context: ContextTypes.DEFAULT_TYPE,
    envelope,
) -> bool:
    if not _is_orchestrator_bot(context):
        return False
    payload_kind = str(envelope.payload.get("kind", "")).strip().lower()
    if payload_kind not in {"calendar.result", "weather.result", "slot_matcher.result"}:
        return False
    if not envelope.correlation_id:
        return False

    pending: dict[str, dict] = context.application.bot_data.setdefault(
        "orchestrator_pending",
        {},
    )
    workflow = pending.pop(envelope.correlation_id, None)
    if workflow is None:
        return False

    if workflow.get("service") == "weather_schedule":
        await _handle_weather_schedule_result(context, workflow, envelope.payload)
        return True

    workflow["results"].append(envelope.payload)
    actions = workflow["actions"]
    index = int(workflow["index"])
    done = envelope.payload.get("ok") is not True or index >= len(actions) - 1
    if not done:
        workflow["index"] = index + 1
        try:
            if workflow.get("service") == "weather":
                await _send_orchestrator_weather_action(context, workflow)
            else:
                await _send_orchestrator_calendar_action(context, workflow)
        except Exception as exc:
            logger.exception("Failed to continue orchestrator workflow")
            await context.bot.send_message(
                chat_id=int(workflow["user_chat_id"]),
                text=f"前一步操作完成了，但继续下一步失败：{exc}",
            )
        return True

    await _finish_orchestrator_workflow(context, workflow)
    return True


async def _handle_weather_schedule_result(
    context: ContextTypes.DEFAULT_TYPE,
    workflow: dict,
    payload: dict,
) -> None:
    user_chat_id = int(workflow["user_chat_id"])
    stage = str(workflow.get("stage", "weather"))

    if payload.get("ok") is not True:
        await context.bot.send_message(
            chat_id=user_chat_id,
            text=f"工作流在 {stage} 阶段失败：{payload.get('error') or '未知错误'}",
        )
        return

    if stage == "weather":
        workflow["weather_results"].append(payload)
        if int(workflow["index"]) < len(workflow["actions"]) - 1:
            workflow["index"] = int(workflow["index"]) + 1
            await _send_orchestrator_weather_action(context, workflow)
            return

        calendar_actions = [
            {
                "action": "free_time",
                "date": result.get("date"),
                "min_duration_minutes": int(workflow.get("duration_minutes") or 60),
            }
            for result in workflow["weather_results"]
            if result.get("date")
        ]
        if not calendar_actions:
            await context.bot.send_message(chat_id=user_chat_id, text="天气查询完成，但没有拿到可用日期。")
            return
        workflow["stage"] = "calendar"
        workflow["actions"] = calendar_actions
        workflow["index"] = 0
        await _send_orchestrator_calendar_action(context, workflow)
        return

    if stage == "calendar":
        workflow["calendar_results"].append(payload)
        if int(workflow["index"]) < len(workflow["actions"]) - 1:
            workflow["index"] = int(workflow["index"]) + 1
            await _send_orchestrator_calendar_action(context, workflow)
            return

        matcher_payload = _build_slot_matcher_payload(workflow)
        if matcher_payload is None:
            await context.bot.send_message(chat_id=user_chat_id, text="没有拿到可匹配的天气时段或空闲时间。")
            return
        workflow["stage"] = "slot_matcher"
        workflow["actions"] = [matcher_payload]
        workflow["index"] = 0
        await _send_orchestrator_slot_matcher_action(context, workflow)
        return

    if stage == "slot_matcher":
        matches = payload.get("matches") or []
        if not matches:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text="我综合天气和你的空闲时间后，没有找到合适的共同时间段。",
            )
            return
        match = matches[0]
        workflow["selected_match"] = match
        workflow["stage"] = "add_event"
        workflow["actions"] = [
            {
                "action": "add_event",
                "title": str(workflow.get("activity_title") or "天气相关安排"),
                "starts_at": match["starts_at"],
                "ends_at": match["ends_at"],
                "on_conflict": "reject",
            }
        ]
        workflow["index"] = 0
        await _send_orchestrator_calendar_action(context, workflow)
        return

    if stage == "add_event":
        await _finish_weather_schedule_workflow(context, workflow, payload)
        return

    await context.bot.send_message(chat_id=user_chat_id, text=f"未知工作流阶段：{stage}")


def _build_slot_matcher_payload(workflow: dict) -> dict | None:
    weather_periods: list[dict] = []
    for result in workflow.get("weather_results", []):
        for period in result.get("periods") or []:
            if isinstance(period, dict):
                weather_periods.append(period)

    calendar_blocks: list[dict] = []
    for result in workflow.get("calendar_results", []):
        for block in result.get("blocks") or []:
            if isinstance(block, dict):
                calendar_blocks.append(block)

    if not weather_periods or not calendar_blocks:
        return None

    return {
        "action": "match_slots",
        "goal": str(workflow.get("goal", "avoid_rain")),
        "duration_minutes": int(workflow.get("duration_minutes") or 60),
        "rain_threshold": int(workflow.get("rain_threshold") or 30),
        "weather_periods": weather_periods,
        "calendar_blocks": calendar_blocks,
    }


async def _finish_weather_schedule_workflow(
    context: ContextTypes.DEFAULT_TYPE,
    workflow: dict,
    add_event_payload: dict,
) -> None:
    user_chat_id = int(workflow["user_chat_id"])
    match = workflow.get("selected_match") or {}
    title = str(workflow.get("activity_title") or "天气相关安排")
    if add_event_payload.get("ok") is True and add_event_payload.get("added"):
        event = add_event_payload.get("event") or {}
        probability = match.get("max_precipitation_probability")
        probability_text = "未知" if probability is None else f"{probability}%"
        await context.bot.send_message(
            chat_id=user_chat_id,
            text=(
                f"已为你安排{title}：\n"
                f"{summarize_calendar_result(add_event_payload)}\n"
                f"匹配依据：{match.get('weather') or '天气未知'}，降水概率最高 {probability_text}。"
            ),
        )

        context_by_chat: dict[int, list[dict]] = context.application.bot_data.setdefault(
            "orchestrator_context_by_chat",
            {},
        )
        recent_context = context_by_chat.setdefault(user_chat_id, [])
        recent_context.append(
            calendar_context_from_result(
                str(workflow.get("user_text", "")),
                workflow.get("actions", []),
                [add_event_payload],
            )
        )
        del recent_context[:-8]
        return

    await context.bot.send_message(
        chat_id=user_chat_id,
        text=summarize_calendar_result(add_event_payload),
    )


async def _finish_orchestrator_workflow(
    context: ContextTypes.DEFAULT_TYPE,
    workflow: dict,
) -> None:
    user_chat_id = int(workflow["user_chat_id"])
    results = workflow["results"]
    actions = workflow["actions"]
    if workflow.get("service") == "weather":
        text = summarize_weather_results(
            results,
            goal=str(workflow.get("goal", "forecast")),
        )
        await context.bot.send_message(chat_id=user_chat_id, text=text)
        return

    lines = [summarize_calendar_result(result) for result in results]
    await context.bot.send_message(chat_id=user_chat_id, text="\n\n".join(lines))

    context_by_chat: dict[int, list[dict]] = context.application.bot_data.setdefault(
        "orchestrator_context_by_chat",
        {},
    )
    recent_context = context_by_chat.setdefault(user_chat_id, [])
    recent_context.append(
        calendar_context_from_result(
            str(workflow.get("user_text", "")),
            actions,
            results,
        )
    )
    del recent_context[:-8]


def _is_orchestrator_bot(context: ContextTypes.DEFAULT_TYPE) -> bool:
    profile = str(context.application.bot_data.get("bot_profile") or "").upper()
    orchestrator_profile = str(
        context.application.bot_data.get("orchestrator_profile") or "C"
    ).upper()
    return bool(profile) and profile == orchestrator_profile


def _looks_like_weather_request(user_text: str) -> bool:
    return bool(re.search(r"(天气|下雨|降水|雨|不下雨|晴|阴天|多云)", user_text))


def _telegram_safe_envelope_text(envelope) -> str:
    text = envelope.to_text()
    if len(text) <= TELEGRAM_TEXT_LIMIT:
        return text

    payload = deepcopy(envelope.payload)
    if payload.get("kind") == "weather.result":
        payload.pop("hours", None)
        payload["truncated"] = True
        payload["note"] = "Response was compacted to fit Telegram message length."
        source = payload.get("source")
        if isinstance(source, dict) and "forecast_url" in source:
            source["forecast_url"] = ""

    compact = replace(envelope, payload=payload)
    compact_text = compact.to_text()
    if len(compact_text) <= TELEGRAM_TEXT_LIMIT:
        return compact_text

    fallback_payload = {
        "kind": str(envelope.payload.get("kind", "result")),
        "service": str(envelope.payload.get("service", "")),
        "action": str(envelope.payload.get("action", "")),
        "ok": bool(envelope.payload.get("ok", False)),
        "truncated": True,
        "error": "Structured response was too long for one Telegram message.",
    }
    return replace(envelope, payload=fallback_payload).to_text()


def _resolve_b2b_target(
    context: ContextTypes.DEFAULT_TYPE,
    target_arg: str,
) -> str | None:
    target = target_arg.strip()
    if not target:
        return None
    if target.startswith("@"):
        return normalize_username(target)

    peers: dict[str, str] = context.application.bot_data.get("bot_peers", {})
    profile = target.upper()
    username = peers.get(profile)
    if username:
        return normalize_username(username)
    return None


def _format_b2b_peers(context: ContextTypes.DEFAULT_TYPE) -> str:
    peers: dict[str, str] = context.application.bot_data.get("bot_peers", {})
    if not peers:
        return "已配置 peers：暂无"
    peer_text = ", ".join(f"{profile}={username}" for profile, username in peers.items())
    return f"已配置 peers：{peer_text}"


async def _own_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    cached = context.application.bot_data.get("bot_username")
    if isinstance(cached, str) and cached:
        return normalize_username(cached)

    me = await context.bot.get_me()
    username = normalize_username(me.username or str(me.id))
    context.application.bot_data["bot_username"] = username
    return username


def _profile_from_argv(argv: list[str]) -> str | None:
    if not argv:
        return None
    if argv[0] in {"--profile", "-p"} and len(argv) >= 2:
        return argv[1]
    if argv[0].startswith("-"):
        return None
    return argv[0]


def _build_llm_clients(settings) -> tuple[LLMClient, LLMClient]:
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai requires CODEX_API_KEY or OPENAI_API_KEY in .env."
            )
        return (
            OpenAIResponsesClient(
                settings.openai_base_url,
                settings.openai_api_key,
                settings.openai_model,
            ),
            OpenAIResponsesClient(
                settings.openai_base_url,
                settings.openai_api_key,
                settings.openai_extract_model,
            ),
        )

    if settings.llm_provider != "ollama":
        raise RuntimeError("LLM_PROVIDER must be 'ollama' or 'openai'.")

    return (
        OllamaClient(settings.ollama_base_url, settings.ollama_model),
        OllamaClient(settings.ollama_base_url, settings.ollama_extract_model),
    )
