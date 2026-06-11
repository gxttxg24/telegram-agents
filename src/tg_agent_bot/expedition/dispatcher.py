from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from telegram import Bot
from telegram.ext import ContextTypes

from .bot_pool import BotPool, RoleAssignment
from .models import StageMessage, StageTurn, WorldState
from .stage import action_keyboard, format_action_panel, format_actor_message


class ActorSender(Protocol):
    async def send_message(self, profile: str, chat_id: int, text: str) -> None:
        ...


@dataclass
class TelegramActorSender:
    bot_pool: BotPool

    async def send_message(self, profile: str, chat_id: int, text: str) -> None:
        identity = self.bot_pool.get(profile)
        if identity is None:
            raise RuntimeError(f"Actor bot profile {profile} is not configured.")
        await Bot(identity.token).send_message(chat_id=chat_id, text=text)


@dataclass
class StageDispatcher:
    role_assignment: RoleAssignment
    sender: ActorSender

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE) -> StageDispatcher:
        bot_data = context.application.bot_data
        bot_pool = BotPool.from_bot_data(bot_data)
        return cls(
            role_assignment=RoleAssignment.from_bot_data(bot_data),
            sender=TelegramActorSender(bot_pool),
        )

    async def send_turn(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        state: WorldState,
        turn: StageTurn,
    ) -> None:
        for narration in turn.narration:
            await context.bot.send_message(chat_id=chat_id, text=narration)

        while True:
            message = turn.queue.next_message(state.epoch)
            if message is None:
                break
            await self.send_actor_message(chat_id, state, message)
            turn.queue.mark_sent(message)

        await context.bot.send_message(
            chat_id=chat_id,
            text=format_action_panel(state),
            reply_markup=action_keyboard(state),
        )

    async def send_actor_message(
        self,
        chat_id: int,
        state: WorldState,
        message: StageMessage,
    ) -> None:
        profile = self.role_assignment.profile_for_role(message.speaker_role_id)
        if profile is None:
            raise RuntimeError(f"No actor profile assigned for role {message.speaker_role_id}.")
        await self.sender.send_message(
            profile,
            chat_id,
            format_actor_message(state, message),
        )
