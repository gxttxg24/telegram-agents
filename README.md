# Telegram Multi-Agent Bot

这是一个基于 Telegram Bot API 的多 bot 协作项目。系统用 4 个 Telegram bot 分工处理自然语言日程管理、天气查询、空闲时间匹配和日程落库。

默认 bot 角色：

```text
A = CalendarBot      日程服务 bot
B = WeatherBot       天气服务 bot
C = OrchestratorBot  总控 bot，用户主要私聊它
D = SlotMatcherBot   时间段匹配 bot
```

用户通常只需要和 C 对话。C 会把自然语言请求解析成结构化任务，再通过 Telegram bot-to-bot 消息调用 A/B/D。

## 运行方式

所有命令都从项目根目录运行：

```powershell
cd d:\R\summer\intern\orion\agent_test
```

安装依赖和本地包：

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e .
```

启动 4 个 bot，建议开 4 个 PowerShell 窗口：

```powershell
.\.venv\Scripts\python -m tg_agent_bot A
.\.venv\Scripts\python -m tg_agent_bot B
.\.venv\Scripts\python -m tg_agent_bot C
.\.venv\Scripts\python -m tg_agent_bot D
```

也可以使用显式 profile 参数：

```powershell
.\.venv\Scripts\python -m tg_agent_bot --profile C
```

注意：

- 不要从 `src/` 目录中启动。项目是标准 `src` layout，应从根目录运行。
- 同一个 Telegram bot token 不能同时被多个 polling 进程稳定消费消息。
- 如果旧版进程还在运行，请先关掉旧进程再启动新版。
- BotFather 中需要为相关 bot 开启 Bot-to-Bot Communication Mode。

## 环境变量

根目录 `.env` 需要配置 4 个 bot 和 Codex API：

```ini
BOT_A_TOKEN=...
BOT_A_USERNAME=@YourCalendarBot

BOT_B_TOKEN=...
BOT_B_USERNAME=@YourWeatherBot

BOT_C_TOKEN=...
BOT_C_USERNAME=@YourOrchestratorBot

BOT_D_TOKEN=...
BOT_D_USERNAME=@YourSlotMatcherBot

ORCHESTRATOR_PROFILE=C
CALENDAR_BOT_PROFILE=A
WEATHER_BOT_PROFILE=B
SLOT_MATCHER_BOT_PROFILE=D

CODEX_BASE_URL=https://ai-internal.orionarm.ai
CODEX_API_KEY=...
CODEX_MODEL=gpt-5.5
CODEX_EXTRACT_MODEL=gpt-5.5
```

不要把真实 token 或 API key 提交到 git。`.env.example` 只应放占位符。

## 常用 Telegram 调试命令

```text
/start
/reset
/b2b_status
/b2b_debug
/b2b_ping B hello
/b2b_calendar A {"action":"free_time","date":"2026-06-10","min_duration_minutes":120}
/b2b_weather B {"location":"上海","date":"2026-06-10"}
```

推荐先对 C 发送 `/b2b_debug`，确认 profile、username、peers 和数据文件路径是否正确。

## 项目结构

```text
agent_test/
  pyproject.toml
  requirements.txt
  .env.example
  docs/
    architecture.md
    b2b_protocol.md
    workflows.md
  src/
    tg_agent_bot/
      __init__.py
      __main__.py
      app.py
      config.py
      llm.py
      memory.py
      b2b/
        __init__.py
        protocol.py
        dispatcher.py
      calendar/
        __init__.py
        models.py
        store.py
        service.py
      orchestrator/
        __init__.py
        planner.py
        workflows.py
        summaries.py
        state.py
      slot_matcher/
        __init__.py
        service.py
      telegram/
        __init__.py
        commands.py
        formatting.py
        handlers.py
        utils.py
      weather/
        __init__.py
        service.py
  tests/
    __init__.py
    test_b2b_protocol.py
    test_calendar_service.py
    test_calendar_store.py
    test_config.py
    test_llm.py
    test_orchestrator_workflows.py
    test_slot_matcher_service.py
    test_telegram_formatting.py
    test_telegram_utils.py
    test_weather_service.py
```

`src/tg_agent_bot.egg-info/` 是执行 `pip install -e .` 后生成的本地打包元数据，不是业务源码。

## docs 目录

`docs/architecture.md`

- 说明重构后的模块分层。
- 概括 `app.py`、`telegram/`、`b2b/`、`orchestrator/`、`calendar/`、`weather/`、`slot_matcher/` 的职责。

`docs/b2b_protocol.md`

- 说明 bot-to-bot JSON envelope 协议。
- 关联 `src/tg_agent_bot/b2b/protocol.py` 和 `src/tg_agent_bot/b2b/dispatcher.py`。

`docs/workflows.md`

- 说明三类主流程：日程请求、天气请求、天气感知的日程安排。

## src 目录

### 根模块

`src/tg_agent_bot/__init__.py`

- Python package 标记文件。

`src/tg_agent_bot/__main__.py`

- `python -m tg_agent_bot` 的入口。
- 调用 `app.main()` 启动 Telegram polling。

`src/tg_agent_bot/app.py`

- 应用组装入口。
- 读取配置，初始化 Telegram `Application`。
- 创建 persistence、memory store、schedule store 和 LLM client。
- 注册命令 handler、私聊文本 handler 和错误 handler。
- 解析命令行 profile：`A/B/C/D` 或 `--profile C`。

`src/tg_agent_bot/config.py`

- 从 `.env` 和环境变量读取配置。
- 支持 profile 专属配置，如 `BOT_A_TOKEN`、`BOT_C_USERNAME`。
- 自动发现 peers：所有 `BOT_*_USERNAME`。
- 生成 profile 隔离的数据文件路径。

`src/tg_agent_bot/llm.py`

- Codex Responses API 客户端。
- 提供普通文本回复和 JSON 规划回复。
- 解析普通 JSON 响应和 `text/event-stream` streaming 响应。
- 负责把对话历史转换成 Responses API input。

`src/tg_agent_bot/memory.py`

- SQLite 对话记忆存储。
- 保存用户和助手消息。
- 为普通聊天和 Orchestrator 上下文提供最近历史。

### telegram/

`src/tg_agent_bot/telegram/__init__.py`

- Telegram 子包标记文件。

`src/tg_agent_bot/telegram/handlers.py`

- `/start`、`/reset` 和私聊文本 handler。
- 私聊文本处理顺序：
  先解析 b2b envelope，再交给 Orchestrator，最后走普通 LLM 回复。
- 记录 Telegram update 异常。

`src/tg_agent_bot/telegram/commands.py`

- 实现 b2b 调试命令。
- `/b2b_ping` 发送 hello request。
- `/b2b_status` 查看 profile、peers、seen ids 和最近事件。
- `/b2b_debug` 查看 getMe、配置 username、chat 和数据路径。
- `/b2b_calendar` 手动发送 CalendarBot payload。
- `/b2b_weather` 手动发送 WeatherBot payload。

`src/tg_agent_bot/telegram/utils.py`

- 解析命令文本中的 payload。
- 保存最近 b2b event。
- 根据 profile 或 `@username` 解析目标 bot。
- 获取并缓存当前 bot username。
- 格式化 peers 调试信息。

`src/tg_agent_bot/telegram/formatting.py`

- 控制发送到 Telegram 的 envelope 文本长度。
- Telegram 文本限制为 4096 字符。
- 对超长天气结果删除小时明细并清空长 URL。
- 仍超长时降级成最小摘要 payload。

### b2b/

`src/tg_agent_bot/b2b/__init__.py`

- 导出 b2b protocol 中的公共函数和类型。

`src/tg_agent_bot/b2b/protocol.py`

- 定义 bot-to-bot JSON envelope。
- 支持 `request` 和 `ack` 两类消息。
- 创建 request、ack、response。
- 解析和校验 envelope。
- 标准化 username。
- 判断 request 是否应该自动 ACK。

`src/tg_agent_bot/b2b/dispatcher.py`

- 接收并分发 b2b envelope。
- 去重、校验 target、校验 sender/source。
- 将 Calendar、Weather、SlotMatcher 请求分发到对应 service。
- 将 service 结果包装成 response 发回 source。
- 将 result 类 ACK 交给 Orchestrator pending workflow。

### calendar/

`src/tg_agent_bot/calendar/__init__.py`

- 导出 calendar 模块的常用对象。

`src/tg_agent_bot/calendar/models.py`

- 日历领域模型兼容/导出模块。

`src/tg_agent_bot/calendar/store.py`

- SQLite 日程和偏好存储。
- 定义 `CalendarEvent`、`ParsedEvent`、`ScheduleRequest`。
- 支持添加、替换、列出、按天查询、冲突检测、删除事件。
- 支持用户偏好保存和读取。
- 提供 `free_time_blocks()` 计算工作时间内空闲块。
- 提供 `pick_schedule_slot()` 自动选择可安排时间。

`src/tg_agent_bot/calendar/service.py`

- CalendarBot 的结构化请求入口。
- 支持：
  `list_events`、`events_on_day`、`free_time`、`add_event`、`schedule_event`、`delete_event`、`set_preference`、`get_preference`、`move_event`、`reschedule_event`。
- 默认冲突策略是 reject。
- `on_conflict=replace` 时可以替换冲突事件。

### weather/

`src/tg_agent_bot/weather/__init__.py`

- Weather 子包标记文件。

`src/tg_agent_bot/weather/service.py`

- WeatherBot 的结构化请求入口。
- 支持 `hourly_forecast` 和 `forecast`。
- 使用 Open-Meteo Geocoding API 将地点转成经纬度。
- 使用 Open-Meteo Forecast API 查询小时级天气。
- 生成小时数据和聚合时段数据。
- 返回降水概率、降水量、天气码、天气文本和温度。

### slot_matcher/

`src/tg_agent_bot/slot_matcher/__init__.py`

- 导出 slot matcher service。

`src/tg_agent_bot/slot_matcher/service.py`

- SlotMatcherBot 的结构化请求入口。
- 输入 CalendarBot 的空闲块和 WeatherBot 的天气时段。
- 输出满足时长和天气目标的候选时间。
- 支持 `avoid_rain`、`prefer_rain`、`forecast`。
- 根据天气偏好和开始时间排序候选项。

### orchestrator/

`src/tg_agent_bot/orchestrator/__init__.py`

- Orchestrator 子包标记文件。

`src/tg_agent_bot/orchestrator/planner.py`

- 调用 LLM 把用户自然语言解析为结构化计划。
- 负责 calendar plan 和 weather plan。
- 支持连续上下文，例如用户后续说“提前一小时”“改到后天”。
- 提供日程结果和天气结果的摘要函数。

`src/tg_agent_bot/orchestrator/workflows.py`

- Orchestrator 多步工作流状态机。
- 判断当前 bot 是否是 C。
- 识别天气类请求。
- 发起 CalendarBot、WeatherBot、SlotMatcherBot 请求。
- 保存 pending workflow。
- 收到 result 后按 correlation id 推进下一步。
- 负责天气感知安排流程：天气 -> 空闲时间 -> 匹配 -> 写入日程 -> 汇报用户。

`src/tg_agent_bot/orchestrator/summaries.py`

- 汇总函数的再导出模块。
- 方便其他模块从较稳定的位置引用摘要能力。

`src/tg_agent_bot/orchestrator/state.py`

- Orchestrator 状态相关代码的预留模块。
- 当前主要状态仍保存在 `Application.bot_data` 中。

## tests 目录

测试使用 `pytest`，配置在 `pyproject.toml`：

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

运行全部测试：

```powershell
.\.venv\Scripts\python -m pytest
```

运行单个测试文件：

```powershell
.\.venv\Scripts\python -m pytest tests\test_orchestrator_workflows.py
```

测试文件说明：

`tests/__init__.py`

- tests package 标记文件。

`tests/test_b2b_protocol.py`

- 测试 b2b envelope 创建、解析、username 标准化、ACK 条件和非法协议校验。

`tests/test_calendar_store.py`

- 测试 SQLite 日程存储。
- 覆盖添加、查询、冲突检测、删除、偏好、空闲时间和自动选 slot。

`tests/test_calendar_service.py`

- 测试 CalendarBot service action。
- 覆盖添加事件、冲突 reject/replace、空闲时间、自动安排、移动、改期、删除和非法 payload。

`tests/test_config.py`

- 测试 profile 配置读取。
- 覆盖 token、username、peers、默认 profile、profile 专属路径、缺 token 和非法 profile。

`tests/test_llm.py`

- 测试 LLM client 的纯解析逻辑。
- 覆盖 Responses URL 拼接、history input 构造、JSON response 和 streaming response 解析。

`tests/test_orchestrator_workflows.py`

- 测试 Orchestrator 工作流。
- 覆盖 C bot 判断、天气意图识别、slot matcher payload 构造、发送 b2b 请求、pending workflow 推进、用户文本触发 workflow、最终汇总和上下文保存。

`tests/test_slot_matcher_service.py`

- 测试 SlotMatcherBot。
- 覆盖避雨、赏雨、forecast、时长不足、排序和非法输入。

`tests/test_telegram_formatting.py`

- 测试 Telegram 文本长度保护。
- 覆盖短 envelope 原样返回、超长 weather result 压缩、仍超长时 fallback。

`tests/test_telegram_utils.py`

- 测试 Telegram 工具函数。
- 覆盖命令 payload、b2b event 保留、target 解析、peers 格式化和 username 缓存。

`tests/test_weather_service.py`

- 测试 WeatherBot service。
- 使用 fake HTTP client，不访问真实 Open-Meteo。
- 覆盖地理编码选择、地点缺失、forecast hourly 校验、小时数据解析、时段聚合和完整请求流程。

当前测试不访问真实 Telegram、Codex API 或 Open-Meteo，适合本地和 CI 默认运行。

## 主要工作流

日程请求：

```text
User -> C
C 调 LLM 解析为 calendar action
C -> A
A 执行日程操作
A -> C
C -> User
```

天气查询：

```text
User -> C
C 调 LLM 解析地点和日期
C -> B
B 查询 Open-Meteo
B -> C
C -> User
```

天气感知安排：

```text
User -> C
C 解析活动、地点、日期、天气目标和时长
C -> B 查询天气
C -> A 查询空闲时间
C -> D 匹配天气时段和空闲时段
C -> A 写入最终日程
C -> User
```

## 依赖

运行依赖：

```text
python-dotenv
python-telegram-bot
httpx
```

测试依赖：

```text
pytest
```

## 开发建议

- 修改代码后先运行 `.\.venv\Scripts\python -m pytest`。
- 新增 service action 时，同步更新 service、orchestrator planner/workflow、b2b payload 和测试。
- Telegram handler 尽量只做收发消息和路由，业务逻辑放在领域 service 或 orchestrator。
- 如果 bot 启动正常但 Telegram 无回复，优先检查旧 polling 进程、profile、`.env`、`/b2b_debug` 和终端 traceback。
