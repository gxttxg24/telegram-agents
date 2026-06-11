from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..telegram.utils import command_payload, normalize_username
from .actions import ActionType, StageAction
from .bot_pool import BotPool, RoleAssignment
from .compiler import compile_user_action, compiled_from_stage_action
from .director import build_turn_for_compiled_action
from .dispatcher import StageDispatcher
from .generator import generate_world_state
from .knowledge import knowledge_snapshot
from .models import StageMessage, StageTurn, WorldState
from .planner import build_directed_turn
from .stage import build_opening_turn, format_controller_opening
from .templates import available_templates, create_world_state


logger = logging.getLogger(__name__)

ROLE_COMMANDS = {
    "mori": "scholar",
    "scholar": "scholar",
    "serena": "mentor",
    "mentor": "mentor",
    "raven": "scout",
    "scout": "scout",
    "pip": "log",
    "log": "log",
    "ailo": "guide",
    "guide": "guide",
}


async def expedition_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    chat_type = str(getattr(update.effective_chat, "type", ""))
    if chat_type == "private":
        await update.effective_message.reply_text(
            "Expedition worlds must be started inside the Telegram group that will "
            "be used as the stage.\n\n"
            "Add the controller bot and actor bots to the same group, then send:\n"
            "/expedition_start@YourControllerBot magic_academy"
        )
        return

    logger.info(
        "Expedition start command received in chat_id=%s chat_type=%s text=%r",
        update.effective_chat.id,
        chat_type or "(unknown)",
        update.effective_message.text,
    )
    template = command_payload(update) or "magic_academy"
    state = create_world_state(template)
    if state is None:
        result = await generate_world_state(
            context.application.bot_data.get("llm"),
            template,
        )
        state = result.state
        if result.error == "llm_not_configured":
            await update.effective_message.reply_text(
                "No built-in template matched that request, and no LLM client is configured. "
                "Starting a simple fallback generated world instead.\n\n"
                f"Built-in templates: {', '.join(available_templates())}"
            )
        elif result.error:
            await update.effective_message.reply_text(
                "The LLM world generator failed, so I started a simple fallback world instead.\n"
                f"Reason: {result.error[:300]}"
            )

    context.application.bot_data.setdefault("expedition_worlds", {})[
        update.effective_chat.id
    ] = state

    await update.effective_message.reply_text(format_controller_opening(state))
    await StageDispatcher.from_context(context).send_turn(
        context,
        update.effective_chat.id,
        state,
        build_opening_turn(state),
    )


async def expedition_debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    me = await context.bot.get_me()
    bot_data = context.application.bot_data
    pool = BotPool.from_bot_data(bot_data)
    assignment = RoleAssignment.from_bot_data(bot_data)
    role_lines = []
    for role, profile in assignment.role_profiles.items():
        identity = pool.get(profile)
        status = "ok" if identity is not None else "missing"
        username = identity.username if identity is not None else "(not configured)"
        role_lines.append(f"- {role}: profile {profile} -> {username} [{status}]")

    chat = update.effective_chat
    chat_label = (
        f"{getattr(chat, 'type', '(unknown)')}:{chat.id}"
        if chat is not None
        else "(unknown)"
    )
    state = expedition_world_for_chat(context, chat.id) if chat is not None else None
    planner_lines = _planner_debug_lines(context, state)
    await update.effective_message.reply_text(
        "expedition debug\n"
        f"getMe: @{me.username} id={me.id}\n"
        f"profile: {bot_data.get('bot_profile') or '(default)'}\n"
        f"chat: {chat_label}\n"
        f"llm client: {'configured' if bot_data.get('llm') is not None else 'missing'}\n"
        f"known bot profiles: {', '.join(sorted(pool.bots)) or '(none)'}\n"
        "role assignment:\n"
        + ("\n".join(role_lines) if role_lines else "- (none)")
        + "\nplanner:\n"
        + "\n".join(planner_lines)
    )


async def expedition_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    state = expedition_world_for_chat(context, update.effective_chat.id)
    if state is None:
        await update.effective_message.reply_text(
            "No expedition is active in this chat. Start one with /expedition_start magic_academy."
        )
        return

    snapshot = knowledge_snapshot(state)
    await update.effective_message.reply_text(_format_knowledge_snapshot(snapshot))


async def expedition_role_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    role_id = _role_from_command_text(update.effective_message.text or "")
    if not role_id:
        return

    state = expedition_world_for_chat(context, update.effective_chat.id)
    if state is None:
        await update.effective_message.reply_text(
            "No expedition is active in this chat. Start one with /expedition_start magic_academy."
        )
        return

    user_text = command_payload(update)
    if not user_text:
        await update.effective_message.reply_text(
            f"Say what you want to ask {role_id}, for example: /mori What do you see?"
        )
        return

    await _handle_user_text(
        update,
        context,
        state,
        user_text,
        addressed_role=role_id,
    )


async def expedition_free_action_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    state = expedition_world_for_chat(context, update.effective_chat.id)
    if state is None:
        await update.effective_message.reply_text(
            "No expedition is active in this chat. Start one with /expedition_start magic_academy."
        )
        return

    user_text = command_payload(update)
    if not user_text:
        await update.effective_message.reply_text(
            "Say what you want to do after the command, for example: "
            "/do Ask Ailo to analyze the scene."
        )
        return

    await _handle_user_text(update, context, state, user_text)


async def expedition_action_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    action = StageAction.from_callback_data(query.data or "")
    chat_id = _callback_chat_id(update)
    if chat_id is None:
        return

    state = expedition_world_for_chat(context, chat_id)
    if state is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="No expedition is active in this chat. Start one with /expedition_start magic_academy.",
        )
        return

    if action is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="This expedition button is no longer recognized.",
        )
        return

    state.record_event(
        "button_action",
        action.semantic_key,
        action_type=action.action_type.value,
        target=action.target,
    )

    if action.action_type is ActionType.INTERRUPT:
        state.flags["stage_status"] = "user_interrupting"
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Stage paused. The expedition is waiting for your interruption.\n"
                "Type what you want to change, ask, or do next."
            ),
        )
        return

    llm = context.application.bot_data.get("llm")
    if llm is None:
        turn = build_turn_for_action(state, action)
    else:
        planner_result = await build_directed_turn(
            llm,
            state,
            compiled_from_stage_action(action),
        )
        turn = planner_result.turn
    await StageDispatcher.from_context(context).send_turn(
        context,
        chat_id,
        state,
        turn,
    )


async def expedition_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return
    if _message_from_bot(update):
        logger.info(
            "Ignoring expedition group text from bot in chat_id=%s.",
            update.effective_chat.id,
        )
        return

    state = expedition_world_for_chat(context, update.effective_chat.id)
    if state is None:
        return

    user_text = (update.effective_message.text or "").strip()
    if not user_text:
        return

    addressed_role = _addressed_role_from_reply(update, context)
    await _handle_user_text(
        update,
        context,
        state,
        user_text,
        addressed_role=addressed_role,
    )


async def _handle_user_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: WorldState,
    user_text: str,
    *,
    addressed_role: str = "",
) -> None:
    if update.effective_chat is None:
        return

    compiled = compile_user_action(state, user_text, addressed_role=addressed_role)
    state.record_event(
        "user_action",
        user_text,
        category=compiled.category.value,
        strategy=compiled.strategy.value,
        action=compiled.action.semantic_key,
        addressed_role=compiled.addressed_role,
    )
    planner_result = await build_directed_turn(
        context.application.bot_data.get("llm"),
        state,
        compiled,
    )
    await StageDispatcher.from_context(context).send_turn(
        context,
        update.effective_chat.id,
        state,
        planner_result.turn,
    )


def expedition_world_for_chat(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> WorldState | None:
    worlds = context.application.bot_data.get("expedition_worlds", {})
    state = worlds.get(chat_id)
    return state if isinstance(state, WorldState) else None


def build_turn_for_action(state: WorldState, action: StageAction) -> StageTurn:
    if action.action_type is ActionType.CHOOSE_PROPOSAL:
        return build_turn_for_compiled_action(state, compiled_from_stage_action(action))

    epoch = state.epoch
    state.advance_turn()
    messages = _messages_for_action(state, action, epoch)
    return StageTurn.create(
        epoch=epoch,
        user_action=action.semantic_key,
        messages=messages,
        buttons=list(state.world_pack.action_buttons),
    )


def _messages_for_action(
    state: WorldState,
    action: StageAction,
    epoch: int,
) -> list[StageMessage]:
    if action.action_type is ActionType.OBSERVE_CLUE:
        _add_clue_once(state, "moon-reactive scale dust")
        return [
            StageMessage(
                speaker_role_id="scholar",
                text=(
                    "The glow is strongest at the footprint edges. That suggests "
                    "moon-reactive scale dust rather than ordinary swamp light."
                ),
                intent="explain_observed_clue",
                epoch=epoch,
            )
        ]

    if action.action_type is ActionType.ASK_ACTOR and action.target == "scholar":
        return [
            StageMessage(
                speaker_role_id="scholar",
                text=(
                    "My current hypothesis is a small nocturnal reptile. The class "
                    "should avoid touching the dust until we know whether it irritates skin."
                ),
                intent="answer_user_question",
                epoch=epoch,
            )
        ]

    if action.action_type is ActionType.ASSIST_ACTOR and action.target == "scout":
        _add_clue_once(state, "broken reeds toward the old watchtower")
        return [
            StageMessage(
                speaker_role_id="scout",
                text=(
                    "I can see broken reeds past the wet path. Something light moved "
                    "toward the watchtower, but it avoided the open mud."
                ),
                intent="scout_ahead",
                epoch=epoch,
            )
        ]

    if action.action_type is ActionType.MOVE_LOCATION:
        state.scene = (
            "The group reaches the low stone path below the old watchtower. "
            "The blue footprints thin out near the stairs, and the wind carries a glassy chime."
        )
        return [
            StageMessage(
                speaker_role_id="mentor",
                text=(
                    "We can approach, but slowly. Nobody enters the tower until Raven "
                    "checks whether the stairs are safe."
                ),
                intent="approve_cautious_movement",
                epoch=epoch,
            ),
            StageMessage(
                speaker_role_id="scout",
                text="The lower steps are damp. I see fresh marks, but not human boot prints.",
                intent="report_new_location",
                epoch=epoch,
            ),
        ]

    if action.action_type is ActionType.RESUME_OBJECTIVE:
        state.objective_stack.resume_latest_paused()
        return [
            StageMessage(
                speaker_role_id="log",
                text="The original footprint investigation is back on top of the task list.",
                intent="resume_objective",
                epoch=epoch,
            )
        ]

    return [
        StageMessage(
            speaker_role_id="mentor",
            text="That action is noted. Let's keep it inside field-class safety rules.",
            intent="fallback_action_response",
            epoch=epoch,
        )
    ]


def _add_clue_once(state: WorldState, clue: str) -> None:
    if clue not in state.clues:
        state.clues.append(clue)
        state.record_event("clue", clue)


def _callback_chat_id(update: Update) -> int | None:
    if update.effective_chat is not None:
        return update.effective_chat.id
    query = update.callback_query
    if query is not None and query.message is not None:
        return query.message.chat_id
    return None


def _message_from_bot(update: Update) -> bool:
    message = update.effective_message
    sender = getattr(message, "from_user", None)
    return bool(getattr(sender, "is_bot", False))


def _role_from_command_text(text: str) -> str:
    first = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    command = first.removeprefix("/").split("@", maxsplit=1)[0].casefold()
    return ROLE_COMMANDS.get(command, "")


def _addressed_role_from_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    message = update.effective_message
    replied = getattr(message, "reply_to_message", None)
    sender = getattr(replied, "from_user", None)
    username = normalize_username(getattr(sender, "username", "") or "")
    if not username:
        return ""

    bot_peers: dict[str, str] = context.application.bot_data.get("bot_peers", {})
    role_profiles: dict[str, str] = context.application.bot_data.get(
        "expedition_role_profiles",
        {},
    )
    username_to_profile = {
        normalize_username(peer_username): profile
        for profile, peer_username in bot_peers.items()
    }
    profile = username_to_profile.get(username)
    if not profile:
        return ""

    for role, role_profile in role_profiles.items():
        if role_profile == profile and role != "controller":
            return role
    return ""


def _planner_debug_lines(
    context: ContextTypes.DEFAULT_TYPE,
    state: WorldState | None,
) -> list[str]:
    if state is None:
        return ["- no active expedition in this chat"]

    last = state.flags.get("last_planner")
    if not isinstance(last, dict):
        return ["- no planner turn recorded yet"]

    used_llm = "yes" if last.get("used_llm") else "no"
    action = last.get("action") or "(unknown)"
    reason = last.get("reason") or ""
    lines = [
        f"- last used llm: {used_llm}",
        f"- last action: {action}",
    ]
    if reason:
        lines.append(f"- fallback reason: {reason}")
    buttons = last.get("buttons")
    if isinstance(buttons, list) and buttons:
        lines.append("- last dynamic buttons: " + ", ".join(str(item) for item in buttons))

    recent_fallbacks = [
        event
        for event in state.history[-8:]
        if event.get("kind") == "planner_fallback"
    ]
    if recent_fallbacks:
        lines.append("- recent fallback event: " + str(recent_fallbacks[-1].get("text", ""))[:200])
    return lines


def _format_knowledge_snapshot(snapshot: dict) -> str:
    def lines_for(title: str, values: list[str]) -> list[str]:
        if not values:
            return [f"{title}: (none)"]
        return [f"{title}:"] + [f"- {value}" for value in values[-6:]]

    lines = [
        "expedition knowledge",
        f"location: {snapshot.get('current_location') or '(unknown)'}",
        f"current action: {snapshot.get('current_action') or '(none)'}",
    ]
    lines.extend(lines_for("known facts", list(snapshot.get("known_facts") or [])))
    lines.extend(lines_for("discoveries", list(snapshot.get("discoveries") or [])))
    lines.extend(lines_for("world rules", list(snapshot.get("world_rules") or [])))
    return "\n".join(lines)
