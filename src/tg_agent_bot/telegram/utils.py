from __future__ import annotations

from telegram import Update


def command_payload(update: Update) -> str:
    if update.effective_message is None or update.effective_message.text is None:
        return ""
    _, _, payload = update.effective_message.text.partition(" ")
    return payload.strip()


def normalize_username(username: str) -> str:
    value = username.strip()
    if not value:
        return ""
    return value if value.startswith("@") else f"@{value}"
