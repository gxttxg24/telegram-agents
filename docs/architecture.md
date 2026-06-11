# Architecture

ExpeditionForge is now centered on a Telegram group stage:

- `app.py` wires settings, persistence, memory, LLM clients, and Telegram handlers.
- `config.py` discovers the Telegram bot pool and expedition role mapping.
- `telegram/` contains the small private-chat handlers and shared Telegram helpers.
- `expedition/` contains world models, templates, the action compiler, Director planning,
  Telegram commands, callback handling, actor dispatch, and bot-pool assignment.
- `memory.py` stores ordinary private-chat context.
- `llm.py` provides the Codex API client used by private chat, world generation, and
  Director planning.

Retired fixed-service modules such as calendar, weather, slot matching, bot-to-bot RPC,
and the old orchestrator workflow are intentionally not part of the active runtime.
