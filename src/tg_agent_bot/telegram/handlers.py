from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from ..llm import LLMClient
from ..memory import MemoryStore


logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "ExpeditionForge controller is online. Add me to a Telegram group with "
        "the actor bots, then start with /expedition_start magic_academy."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    memory: MemoryStore = context.application.bot_data["memory"]
    memory.clear(update.effective_chat.id)
    await update.effective_message.reply_text("This private chat memory has been cleared.")


async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    user_text = update.effective_message.text or ""
    if not user_text.strip():
        return

    memory: MemoryStore = context.application.bot_data["memory"]
    llm: LLMClient | None = context.application.bot_data["llm"]
    history_turns: int = context.application.bot_data["history_turns"]
    chat_id = update.effective_chat.id

    if llm is None:
        await update.effective_message.reply_text(
            "I received your message, but no Codex API client is configured. "
            "Set CODEX_API_KEY and CODEX_BASE_URL to enable private chat replies."
        )
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    history = memory.recent(chat_id, limit=history_turns * 2)

    try:
        reply = await llm.reply(history=history, user_text=user_text)
    except Exception:
        logger.exception("LLM request failed")
        reply = (
            "I received your message, but the Codex API request failed. "
            "Check CODEX_API_KEY, CODEX_BASE_URL, and model settings."
        )

    memory.add(chat_id, "user", user_text)
    memory.add(chat_id, "assistant", reply)
    await update.effective_message.reply_text(reply)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Telegram update failed", exc_info=context.error)
