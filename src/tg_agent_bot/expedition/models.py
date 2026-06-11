from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ObjectiveStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class SpeakerQueueStatus(StrEnum):
    PENDING = "pending"
    SPEAKING = "speaking"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class PluginStatus(StrEnum):
    IMPLEMENTED = "implemented"
    PLACEHOLDER = "placeholder"
    DISABLED = "disabled"


@dataclass
class RoleCard:
    role_id: str
    display_name: str
    archetype: str
    personality: str
    public: bool = True
    bot_username: str | None = None
    responsibilities: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "display_name": self.display_name,
            "archetype": self.archetype,
            "personality": self.personality,
            "public": self.public,
            "bot_username": self.bot_username,
            "responsibilities": list(self.responsibilities),
            "abilities": list(self.abilities),
            "constraints": list(self.constraints),
        }


@dataclass
class WorldPack:
    world_id: str
    name: str
    world_type: str
    tone: str
    user_role: str
    starting_objective: str
    location: str
    ecology: list[str]
    anomalies: list[str]
    risk_level: str
    roles: list[RoleCard]
    rules: list[str]
    opening_scene: str
    initial_clues: list[str]
    action_buttons: list[str]
    opening_narration: list[str] = field(default_factory=list)
    opening_messages: list[dict[str, str]] = field(default_factory=list)

    def role_by_id(self, role_id: str) -> RoleCard | None:
        normalized = role_id.strip().casefold()
        for role in self.roles:
            if role.role_id.casefold() == normalized:
                return role
        return None


@dataclass
class Objective:
    objective_id: str
    title: str
    status: ObjectiveStatus = ObjectiveStatus.ACTIVE
    parent_id: str | None = None
    notes: list[str] = field(default_factory=list)
    absorbed_clues: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, title: str, *, parent_id: str | None = None) -> Objective:
        return cls(objective_id=str(uuid4()), title=title, parent_id=parent_id)


@dataclass
class ObjectiveStack:
    objectives: list[Objective] = field(default_factory=list)

    @classmethod
    def with_initial(cls, title: str) -> ObjectiveStack:
        return cls([Objective.create(title)])

    @property
    def active(self) -> Objective | None:
        for objective in reversed(self.objectives):
            if objective.status is ObjectiveStatus.ACTIVE:
                return objective
        return None

    def push(
        self,
        title: str,
        *,
        pause_current: bool = True,
        absorbed_clues: list[str] | None = None,
    ) -> Objective:
        current = self.active
        if current is not None and pause_current:
            current.status = ObjectiveStatus.PAUSED
        objective = Objective.create(
            title,
            parent_id=current.objective_id if current is not None else None,
        )
        objective.absorbed_clues = list(absorbed_clues or [])
        self.objectives.append(objective)
        return objective

    def resume_latest_paused(self) -> Objective | None:
        current = self.active
        if current is not None:
            current.status = ObjectiveStatus.PAUSED
        for objective in reversed(self.objectives):
            if objective.status is ObjectiveStatus.PAUSED and objective is not current:
                objective.status = ObjectiveStatus.ACTIVE
                return objective
        if current is not None:
            current.status = ObjectiveStatus.ACTIVE
        return current


@dataclass
class WorldState:
    world_pack: WorldPack
    scene: str
    objective_stack: ObjectiveStack
    epoch: int = 1
    turn_number: int = 0
    clues: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_pack(cls, world_pack: WorldPack) -> WorldState:
        return cls(
            world_pack=world_pack,
            scene=world_pack.opening_scene,
            objective_stack=ObjectiveStack.with_initial(world_pack.starting_objective),
            clues=list(world_pack.initial_clues),
        )

    @property
    def active_objective(self) -> Objective | None:
        return self.objective_stack.active

    def advance_turn(self) -> int:
        self.turn_number += 1
        return self.turn_number

    def record_event(self, kind: str, text: str, **data: Any) -> None:
        self.history.append(
            {
                "turn_number": self.turn_number,
                "epoch": self.epoch,
                "kind": kind,
                "text": text,
                **data,
            }
        )


@dataclass
class StageMessage:
    speaker_role_id: str
    text: str
    intent: str
    epoch: int
    interruptible: bool = True
    sent: bool = False


@dataclass
class SpeakerQueue:
    turn_id: str
    epoch: int
    messages: list[StageMessage]
    status: SpeakerQueueStatus = SpeakerQueueStatus.PENDING
    cursor: int = 0
    cancel_reason: str = ""

    @classmethod
    def create(cls, *, epoch: int, messages: list[StageMessage]) -> SpeakerQueue:
        return cls(turn_id=str(uuid4()), epoch=epoch, messages=messages)

    def next_message(self, current_epoch: int) -> StageMessage | None:
        if self.status is SpeakerQueueStatus.CANCELLED:
            return None
        if self.epoch != current_epoch:
            self.cancel("stale_epoch")
            return None
        if self.cursor >= len(self.messages):
            self.status = SpeakerQueueStatus.COMPLETED
            return None
        self.status = SpeakerQueueStatus.SPEAKING
        message = self.messages[self.cursor]
        self.cursor += 1
        return message

    def mark_sent(self, message: StageMessage) -> None:
        message.sent = True
        if self.cursor >= len(self.messages):
            self.status = SpeakerQueueStatus.COMPLETED

    def cancel(self, reason: str = "user_interrupt") -> None:
        self.status = SpeakerQueueStatus.CANCELLED
        self.cancel_reason = reason


@dataclass
class StageTurn:
    turn_id: str
    epoch: int
    user_action: str
    queue: SpeakerQueue
    narration: list[str] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        epoch: int,
        user_action: str,
        messages: list[StageMessage],
        buttons: list[str],
        narration: list[str] | None = None,
    ) -> StageTurn:
        queue = SpeakerQueue.create(epoch=epoch, messages=messages)
        return cls(
            turn_id=queue.turn_id,
            epoch=epoch,
            user_action=user_action,
            queue=queue,
            narration=list(narration or []),
            buttons=list(buttons),
        )


@dataclass(frozen=True)
class PluginDefinition:
    name: str
    status: PluginStatus
    capabilities: tuple[str, ...] = ()
    fallback_message: str = ""

    def available(self) -> bool:
        return self.status is PluginStatus.IMPLEMENTED


@dataclass
class PluginRegistry:
    plugins: dict[str, PluginDefinition] = field(default_factory=dict)

    def register(
        self,
        name: str,
        *,
        status: PluginStatus,
        capabilities: list[str] | tuple[str, ...] = (),
        fallback_message: str = "",
    ) -> PluginDefinition:
        plugin = PluginDefinition(
            name=name,
            status=status,
            capabilities=tuple(capabilities),
            fallback_message=fallback_message,
        )
        self.plugins[name] = plugin
        return plugin

    def can_use(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        return plugin.available() if plugin is not None else False

    @classmethod
    def expedition_defaults(cls) -> PluginRegistry:
        registry = cls()
        registry.register(
            "pptx_generator",
            status=PluginStatus.PLACEHOLDER,
            capabilities=["generate_report_outline", "generate_slide_content"],
            fallback_message="Can generate outline text, but not a real .pptx file yet.",
        )
        return registry
