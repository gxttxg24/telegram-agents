# ExpeditionForge / Telegram Bot Stage

ExpeditionForge is a Telegram-native multi-bot expedition runtime.

The intended shape is one Telegram group with several real bot identities:
each actor bot plays one expedition character, while a hidden runtime acts as
Director and decides which character should speak next.

Example role assignment:

```text
@aster_test_rili_bot      -> Serena / field mentor
@aster_test_tianqi_bot    -> Mori / creature scholar
@aster_test_pipei_bot     -> Raven / scout
@aster_test_e_bot         -> Pip / expedition recorder
@aster_test_f_bot         -> Ailo / forest guide
@aster_test_zongkong_bot  -> StageControllerBot
```

The StageControllerBot receives Telegram commands, callback buttons, and group
text. Actor bots do not run their own polling loops. The controller runtime uses
their tokens to send character messages into the same group.

## Current Modules

```text
src/tg_agent_bot/expedition/
  actions.py      controlled button semantics and callback data
  bot_pool.py     bot token discovery and role assignment
  commands.py     Telegram command, callback, and group text handlers
  compiler.py     small rule-based Action Compiler for free text
  director.py     Director turn builder and rule-aware responses
  dispatcher.py   sends role messages through real actor bot tokens
  planner.py      structured LLM Director Planner with validation/fallback
  models.py       WorldPack, WorldState, objectives, queue, turns
  stage.py        opening turn and controller panel formatting
  templates.py    fixed world templates
```

The current fixed template is `magic_academy`.

## Bot Configuration

You can keep using bots A-F. Recommended `.env` shape:

```ini
BOT_A_TOKEN=...
BOT_A_USERNAME=@aster_test_rili_bot

BOT_B_TOKEN=...
BOT_B_USERNAME=@aster_test_tianqi_bot

BOT_C_TOKEN=...
BOT_C_USERNAME=@aster_test_zongkong_bot

BOT_D_TOKEN=...
BOT_D_USERNAME=@aster_test_pipei_bot

BOT_E_TOKEN=...
BOT_E_USERNAME=@aster_test_e_bot

BOT_F_TOKEN=...
BOT_F_USERNAME=@aster_test_f_bot

EXPEDITION_CONTROLLER_PROFILE=C
EXPEDITION_MENTOR_PROFILE=A
EXPEDITION_SCHOLAR_PROFILE=B
EXPEDITION_SCOUT_PROFILE=D
EXPEDITION_LOG_PROFILE=E
EXPEDITION_GUIDE_PROFILE=F
```

Run only the controller profile:

```powershell
.\.venv\Scripts\python -m tg_agent_bot C
```

All actor bots must be added to the same Telegram group. Do not run multiple
polling processes for the same token.

## How To Try It

In the Telegram group, send the command to the controller bot:

```text
/expedition_start@aster_test_zongkong_bot magic_academy
```

Or start a generated world by describing the expedition:

```text
/expedition_start@aster_test_zongkong_bot cozy mushroom train mystery
/expedition_start@aster_test_zongkong_bot 我想玩一个轻松一点的魔法学院夜间生物观察
```

If an LLM client is configured, the controller generates a fresh World Pack
with a world name, user role, objective, location, clues, role cards, rules,
opening scene, and buttons. If no LLM client is configured, it starts a simple
fallback generated world instead of failing.

The controller sends the opening panel. Then the dispatcher asks the real actor
bots to speak:

```text
StageControllerBot:
Expedition started: Starcedar Academy: Mistfeather Grove Night Observation
Turn 1
Location: Mistfeather Grove wetland entrance
Objective: Investigate three nights of blue glowing footprints.

Serena:
Remember, tonight's assignment is observation, not capture...

Mori:
The edge of each footprint carries a faint scale-dust reaction...

StageControllerBot:
Your move.
[Inspect footprints] [Ask Mori] [Send Raven ahead] [Go to the old watchtower] [Wait]
```

You can also run:

```text
/expedition_debug@aster_test_zongkong_bot
```

This reports the active controller profile, known bot profiles, and role
assignment without printing token values.

## Talking To A Character

Telegram group privacy matters:

- Button clicks always reach the controller.
- Plain group text only reaches the controller if the controller bot can see
  group messages. In BotFather this is controlled by the controller bot's group
  privacy setting.
- Replies to actor bot messages only reach the controller if Telegram delivers
  those replies to the controller. With privacy enabled, this is usually not
  guaranteed.

The most reliable MVP entry point is a role command sent in the group:

```text
/mori What do you think about this dust?
/serena Should we continue?
/raven Scout the watchtower path.
/pip Summarize our clues.
/ailo Where should we go next?
```

These commands are handled by the StageControllerBot, then dispatched to the
real actor bot assigned to that role. For example, `/mori ...` schedules the
scholar role, so Mori's bot sends the reply.

If the controller can see free group text, messages that mention Mori or ask the
scholar are also routed to the scholar. If the controller can see reply context,
replying to an actor bot message routes the next turn to that actor's role.

## Button Semantics

Button labels may change, but backend actions are controlled.

Examples:

```text
Inspect footprints       -> observe_clue:footprints
Ask Mori                 -> ask_actor:scholar
Send Raven ahead         -> assist_actor:scout
Go to the old watchtower -> move_location:old_watchtower
Wait                     -> interrupt
Resume original          -> resume_objective
Generate report outline  -> generate_report_outline:ppt_outline
Follow Raven's route     -> choose_proposal:scout_bold
```

Telegram callback data uses this format:

```text
expedition:action:<action_type>[:target]
```

The callback handler records the action and asks the Director to schedule at
most one or two actor messages.

When characters disagree, the LLM planner can return proposal buttons. These
buttons are still controlled callbacks such as `choose_proposal:scout_bold`,
`choose_proposal:mentor_safe`, `choose_proposal:scholar_rule`, or
`choose_proposal:log_synthesis`, so the user can choose a route without letting
arbitrary button text become backend behavior.

If an LLM client is configured, button actions go through the structured LLM
Director Planner. If no LLM client is available, the runtime falls back to the
deterministic MVP responses.

## LLM Director Planner

The runtime now has a structured LLM planning layer.

The LLM receives:

- World pack summary
- Current scene
- Active objective
- Current clues
- Recent history
- The compiled user action or button semantic
- Public role cards
- Allowed action types

The LLM must return JSON only:

```json
{
  "scene_update": "string",
  "objective_update": "string",
  "clues_added": ["string"],
  "risk_delta": 0,
  "speaker_messages": [
    {
      "role_id": "scholar",
      "intent": "explain_clue",
      "text": "short in-character message"
    }
  ],
  "buttons": [
    {
      "label": "Compare spiral grain",
      "action_type": "observe_clue",
      "target": "spiral_grain"
    }
  ]
}
```

The code validates the plan before dispatching it:

- Only public roles from the current world may speak.
- At most two actor messages are sent per turn.
- Each role can speak at most once per turn.
- Button action types must be from the controlled `ActionType` whitelist.
- Unknown actions, unknown roles, and oversized text are discarded.
- A wait/interrupt button is always preserved or added.
- If the LLM fails or returns an unusable plan, the deterministic Director is
  used as fallback.

This means the LLM creates the next story beat and dynamic buttons, but the
runtime still controls the Telegram stage rules.

## Free Text Actions

Group text is no longer just logged. It now passes through a small rule-based
Action Compiler and then into the Director.

Currently supported examples:

- Asking Mori or the scholar about something dispatches Mori.
- Role commands such as `/mori ...` force the next turn to address that role.
- Saying `wait`, `pause`, or similar enters interruption mode.
- Asking for a PPT/report/computer-style pivot reframes the objective into a
  field report and asks recorder/guide roles to respond.
- Asking to turn Mori into a computer and let ChatGPT analyze the scene is
  treated as a major pivot. The runtime does not claim to call a real ChatGPT
  plugin yet; Mori reframes it as an in-world field-analysis terminal.
- Dangerous absurd actions such as trying to cause a methane explosion to fly
  into the sky are handled with `no_but`: the system refuses the dangerous
  method, preserves the fantasy goal, and rewrites it as a safe marsh-spirit
  lift to a cloud wetland.
- Conceptual errors such as making water by writing H and O are handled with
  `explain_then_offer`: the scholar explains the error and offers playable
  alternatives.

With an LLM client configured, the compiled action is passed into the LLM
Director Planner so the next scene, role messages, clues, and buttons can change
dynamically. Without an LLM client, the deterministic fallback remains active.

## Current Limits

- Only the `magic_academy` template is fully wired.
- Free-text classification is still rule-based before the LLM planner sees it.
- Reply-to-specific-bot, dice checks, polls, pinned objective panels, and real
  plugin tools are not implemented yet.
- The LLM Director Planner is now implemented, but it is still a single-turn
  planner rather than a long-horizon encounter system.
- Actor bots send messages through their tokens, but they do not independently
  listen or decide what to say.

## Tests

Run expedition-related tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_expedition_director.py tests\test_expedition_commands.py tests\test_expedition_dispatcher.py tests\test_expedition_stage.py
```

Run all tests:

```powershell
.\.venv\Scripts\python -m pytest
```
