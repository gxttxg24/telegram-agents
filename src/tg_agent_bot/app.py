
from __future__ import annotations

import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    PersistenceInput,
    filters,
)

from .b2b.protocol import normalize_username
from .calendar.store import ScheduleStore
from .config import load_settings
from .llm import CodexAPIClient, LLMClient
from .memory import MemoryStore
from .orchestrator.runtime_state import OrchestratorStateStore
from .telegram.commands import b2b_calendar, b2b_debug, b2b_ping, b2b_status, b2b_weather
from .telegram.handlers import error_handler, handle_private_text, reset, start


logger = logging.getLogger(__name__)

def build_application(profile: str | None = None) -> Application:
    settings = load_settings(profile)
    persistence = PicklePersistence(
        filepath=settings.telegram_persistence_file,
        store_data=PersistenceInput(bot_data=False),
    )
    memory = MemoryStore(settings.memory_db)
    schedule = ScheduleStore(settings.schedule_db)
    orchestrator_state = OrchestratorStateStore(settings.orchestrator_state_db)
    llm, extract_llm = _build_llm_clients(settings)  # REVIEW: 这个函数只被调一次，没必要抽成独立函数。直接内联更清晰。

    application = (
        ApplicationBuilder()
        .token(settings.telegram_token)
        .persistence(persistence)
        .concurrent_updates(False)  # REVIEW: 关掉并发是因为下面的状态管理不是线程安全的。这只能支撑单用户场景，多用户时所有请求会串行排队。
        .build()
    )

    # REVIEW: 把 15 个对象塞进一个 untyped dict 是典型的 service locator 反模式。
    # 所有 handler 里都要写 context.application.bot_data["memory"] 这种魔法字符串访问，
    # 没有 IDE 补全，拼错 key 不会报错，mypy 也帮不了你。
    # 建议: 定义一个 @dataclass BotContext 把这些字段类型化，
    # 或者至少用一个 TypedDict 约束 bot_data 的 key。
    application.bot_data["memory"] = memory
    application.bot_data["schedule"] = schedule
    application.bot_data["llm"] = llm
    application.bot_data["extract_llm"] = extract_llm
    application.bot_data["history_turns"] = settings.history_turns
    application.bot_data["b2b_events"] = []
    application.bot_data["bot_profile"] = settings.bot_profile
    application.bot_data["orchestrator_profile"] = settings.orchestrator_profile
    application.bot_data["calendar_bot_profile"] = settings.calendar_bot_profile
    application.bot_data["weather_bot_profile"] = settings.weather_bot_profile
    application.bot_data["slot_matcher_bot_profile"] = settings.slot_matcher_bot_profile
    application.bot_data["orchestrator_state"] = orchestrator_state
    application.bot_data["configured_bot_username"] = normalize_username(settings.telegram_username)
    application.bot_data["bot_peers"] = {
        profile: normalize_username(username)
        for profile, username in settings.bot_peers.items()
    }
    application.bot_data["settings_summary"] = {
        "persistence": str(settings.telegram_persistence_file),
        "memory_db": str(settings.memory_db),
        "schedule_db": str(settings.schedule_db),
        "orchestrator_state_db": str(settings.orchestrator_state_db),
    }

    private_chat = filters.ChatType.PRIVATE
    application.add_handler(CommandHandler("start", start, filters=private_chat))
    application.add_handler(CommandHandler("reset", reset, filters=private_chat))
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
    logger.info(
        "Orchestrator state: db=%s pending=%s seen=%s",
        settings_summary.get("orchestrator_state_db", ""),
        application.bot_data["orchestrator_state"].pending_count(),
        application.bot_data["orchestrator_state"].seen_count(),
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def _profile_from_argv(argv: list[str]) -> str | None:
    # REVIEW: 手写 argv 解析是典型的 AI 生成味道——看起来能工作但不完整。
    # 没有 --help, 不报错未知参数, 静默忽略 "-x" 类 flag。
    # 3 行 argparse 就能解决，还自带帮助和错误信息。
    if not argv:
        return None
    if argv[0] in {"--profile", "-p"} and len(argv) >= 2:
        return argv[1]
    if argv[0].startswith("-"):
        return None
    return argv[0]


def _build_llm_clients(settings) -> tuple[LLMClient, LLMClient]:
    if not settings.codex_api_key:
        raise RuntimeError("CODEX_API_KEY is required in .env.")
    if not settings.codex_base_url:
        raise RuntimeError("CODEX_BASE_URL is required in .env.")
    return (
        CodexAPIClient(
            settings.codex_base_url,
            settings.codex_api_key,
            settings.codex_model,
        ),
        CodexAPIClient(
            settings.codex_base_url,
            settings.codex_api_key,
            settings.codex_extract_model,
        )
    )
