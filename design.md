# ExpeditionForge / Telegram Bot Stage Design

This document outlines a step-by-step implementation plan for a Telegram-native multi-bot expedition world runtime.

## Goal

Build **ExpeditionForge / Telegram Bot Stage**: a Telegram-native multi-bot adventure runtime where a Telegram group becomes the exploration stage.

Users provide a set of Telegram bots. The system generates an original expedition world and assigns bots to visible roles such as mentor, scholar, scout, guide, recorder, healer, or mapmaker. A Director-controlled runtime manages pacing, buttons, replies, dice checks, interruptions, objectives, and world consistency.

The system is not a fixed collection of utility bots and not an arbitrary code-generation system. Its core is:

- Dynamic expedition world generation
- Multi-bot roleplay in Telegram groups
- Director-controlled semi-turn-based pacing
- User interruption and story pivots
- Action Compiler for open-ended player actions
- Consistency Arbiter for world rules and safety boundaries
- Objective Stack for task rewriting and recovery
- SpeakerQueue for controlled bot speech
- PluginRegistry for real-tool placeholders

Most important principle:

> The user's imagination can change the world, but the world responds through its own rules.

## Step 1: Expedition Data Models

Implement the pure Python core models first, without Telegram integration.

Core models:

- `WorldPack`
- `WorldState`
- `RoleCard`
- `ObjectiveStack`
- `StageTurn`
- `SpeakerQueue`
- `PluginRegistry`

Goal: tests can create a "Mistfeather Grove night observation class", advance one turn, and persist state.

## Step 2: Fixed Template Demo

Do not start with LLM-generated worlds. Add 2-3 built-in world templates:

- Magic academy field class
- Alien ecology survey team
- Black forest folklore investigation

Goal: `/expedition_start magic_academy` creates a fixed World Pack and opening scene.

## Step 3: Telegram Group Stage

Add the Telegram-native stage experience:

- Group chat handler
- DirectorBot narration
- Visible actor bot messages
- Inline action buttons
- `[Wait]` / `[等等]` interrupt button
- At most 1-2 role messages per turn

Goal: a group chat can show one semi-turn-based expedition opening, not a hidden RPC pipeline.

## Step 4: SpeakerQueue And Interrupts

Implement a real speech queue:

- Each message has `turn_id` and `epoch`
- Clicking `[等等]` or typing "停", "等等", or "我改主意" cancels remaining queued speech
- Runtime enters `USER_INTERRUPTING`
- Director asks what the user wants to add or change

Goal: bots do not spam the group, and the user can actually interrupt.

## Step 5: Button Semantics

Buttons may have dynamic labels, but their backend semantics must be controlled.

Examples:

- `[检查足迹]` -> `observe clue`
- `[询问学者]` -> `ask actor`
- `[派斥候侦查]` -> `assist actor`
- `[前往旧瞭望塔]` -> `move location`
- `[恢复原探险]` -> `resume_objective`

Goal: buttons are flexible in wording but map to safe, known action types.

## Step 6: Action Compiler V1

Start with a rule-based compiler before a full LLM compiler.

Support:

- Ordinary actions
- Asking a specific role
- Moving to a place
- Observing a clue
- Interrupt / pause
- Keyword-based major pivot detection

Goal: if the user says "我先问学者这种鳞粉有没有毒", the next turn prioritizes ScholarBot.

## Step 7: Consistency Arbiter V1

Handle absurd, dangerous, or conceptually mistaken actions.

Response strategies:

- `yes_and`
- `yes_but`
- `no_but`
- `explain_then_offer`

Goal: safely handle examples like "引爆沼气上天" and "写 H 和 O 得到水" without boring rejection or unsafe instructions.

## Step 8: Objective Stack And Story Pivot

Implement major interruptions:

- Pause the old objective
- Create a new active objective
- Absorb old clues into the new objective
- Reassign role duties
- Generate new buttons

Goal: support the key demo: "把向导变成电脑，做环境调研 PPT".

## Step 9: World Pack Generator

Introduce LLM generation for original worlds based on user descriptions.

Generate:

- World name
- User identity
- Role cards
- Expedition objective
- Location
- Current scene
- Initial clues
- Style rules
- Risk level

Goal: user input like "我想玩轻松一点的魔法学院夜间生物观察" produces an original expedition pack.

## Step 10: PluginRegistry Placeholders

Implement the registry before real plugins.

Example plugin states:

- `pptx_generator: placeholder`
- `map_generator: placeholder`
- `real_weather: disabled`
- `file_exporter: placeholder`

Goal: when the user asks for a real PPT, the system can honestly fall back to an outline and slide content instead of pretending to generate a file.

## Step 11: Multi-Bot Token Pool

Move from fixed A/B/C/D profiles toward a dynamic bot pool.

Example:

```ini
BOT_POOL_1_TOKEN=...
BOT_POOL_2_TOKEN=...
BOT_POOL_3_TOKEN=...
```

Goal: the same bot pool can be reassigned to different roles in different expedition worlds.

## Step 12: Retire Old Business Modules

Once the ExpeditionForge path works, remove or archive the old fixed-service modules:

- `calendar/`
- `weather/`
- `slot_matcher/`
- old `orchestrator/`

Update tests, README, commands, and documentation at the same time.

## First Milestone

The first milestone should cover Steps 1-4:

> Fixed magic academy expedition template + Telegram group semi-turn loop + inline buttons + interruptible SpeakerQueue.

This milestone already demonstrates the Telegram-native core experience.
