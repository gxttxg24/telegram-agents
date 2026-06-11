
from __future__ import annotations

import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    PersistenceInput,
    filters,
)

from .config import load_settings
from .expedition.commands import (
    expedition_debug,
    expedition_free_action_command,
    expedition_group_text,
    expedition_knowledge,
    expedition_role_command,
    expedition_start,
)
from .expedition.commands import expedition_action_callback
from .llm import CodexAPIClient, LLMClient
from .memory import MemoryStore
from .telegram.handlers import error_handler, handle_private_text, reset, start
from .telegram.utils import normalize_username


logger = logging.getLogger(__name__)

def build_application(profile: str | None = None) -> Application:
    settings = load_settings(profile)
    persistence = PicklePersistence(
        filepath=settings.telegram_persistence_file,
        store_data=PersistenceInput(bot_data=False),
    )
    memory = MemoryStore(settings.memory_db)
    llm, extract_llm = _build_llm_clients(settings)

    application = (
        ApplicationBuilder()
        .token(settings.telegram_token)
        .persistence(persistence)
        .concurrent_updates(False)
        .build()
    )

    application.bot_data["memory"] = memory
    application.bot_data["llm"] = llm
    application.bot_data["extract_llm"] = extract_llm
    application.bot_data["history_turns"] = settings.history_turns
    application.bot_data["bot_profile"] = settings.bot_profile
    application.bot_data["bot_tokens"] = dict(settings.bot_tokens)
    application.bot_data["configured_bot_username"] = normalize_username(settings.telegram_username)
    application.bot_data["bot_peers"] = {
        profile: normalize_username(username)
        for profile, username in settings.bot_peers.items()
    }
    application.bot_data["expedition_role_profiles"] = dict(settings.expedition_role_profiles)
    application.bot_data["settings_summary"] = {
        "persistence": str(settings.telegram_persistence_file),
        "memory_db": str(settings.memory_db),
    }

    private_chat = filters.ChatType.PRIVATE
    group_chat = filters.ChatType.GROUPS
    application.add_handler(CommandHandler("start", start, filters=private_chat))
    application.add_handler(CommandHandler("reset", reset, filters=private_chat))
    application.add_handler(CommandHandler("expedition_start", expedition_start))
    application.add_handler(CommandHandler("expedition_debug", expedition_debug))
    application.add_handler(CommandHandler("expedition_knowledge", expedition_knowledge))
    application.add_handler(
        CommandHandler(
            ["do", "act", "expedition_do"],
            expedition_free_action_command,
            filters=group_chat,
        )
    )
    application.add_handler(
        CommandHandler(
            ["mori", "scholar", "serena", "mentor", "raven", "scout", "pip", "log", "ailo", "guide"],
            expedition_role_command,
            filters=group_chat,
        )
    )
    application.add_handler(CallbackQueryHandler(expedition_action_callback, pattern=r"^expedition:action:"))
    application.add_handler(
        MessageHandler(
            group_chat & filters.TEXT & ~filters.COMMAND,
            expedition_group_text,
        )
    )
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
        "Bot storage: persistence=%s memory=%s",
        settings_summary.get("persistence", ""),
        settings_summary.get("memory_db", ""),
    )
    logger.info(
        "Expedition roles: %s",
        application.bot_data.get("expedition_role_profiles", {}),
    )
    logger.info(
        "Configured bot profiles with tokens: %s",
        sorted(application.bot_data.get("bot_tokens", {})),
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def _profile_from_argv(argv: list[str]) -> str | None:
    if not argv:
        return None
    if argv[0] in {"--profile", "-p"} and len(argv) >= 2:
        return argv[1]
    if argv[0].startswith("-"):
        return None
    return argv[0]


def _build_llm_clients(settings) -> tuple[LLMClient | None, LLMClient | None]:
    if not settings.codex_api_key or not settings.codex_base_url:
        logger.warning(
            "Codex API is not configured; LLM features will use deterministic fallbacks."
        )
        return None, None
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
