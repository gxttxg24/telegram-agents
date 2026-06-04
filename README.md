# Telegram Multi-Agent Bot

这是一个基于 Telegram Bot API 的多 bot 协作实验项目。系统用 4 个 bot 分工完成自然语言日程安排、天气查询、空闲时间匹配和最终落库。

默认角色：

```text
A = CalendarBot      日程服务
B = WeatherBot       天气服务
C = OrchestratorBot  总控和自然语言理解
D = SlotMatcherBot   时间段匹配服务
```

## 快速启动

`.env` 中配置四个 bot：

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

启动四个进程：

```powershell
.\.venv\Scripts\python -m tg_agent_bot A
.\.venv\Scripts\python -m tg_agent_bot B
.\.venv\Scripts\python -m tg_agent_bot C
.\.venv\Scripts\python -m tg_agent_bot D
```

Profile 模式会自动分开数据文件，例如 `data/bot_schedule_a.sqlite3`、`data/telegram_persistence_c.pickle`。

BotFather 中需要为相关 bot 开启 Bot-to-Bot Communication Mode。

## 项目结构

```text
tg_agent_bot/
  bot.py                         Telegram handler、profile 启动、总控状态机
  b2b.py                         bot-to-bot JSON envelope、去重、防循环
  config.py                      .env 配置、A/B/C/D profile 发现
  llm.py                         Codex API client
  schedule.py                    SQLite 日程表、空闲时间、冲突检测

  bots/calendar/service.py       Bot A: CalendarBot 后端
  bots/weather/service.py        Bot B: WeatherBot 后端
  bots/orchestrator/planner.py   Bot C: 总控 LLM 规划和结果摘要
  bots/slot_matcher/service.py   Bot D: SlotMatcherBot 后端
```

## 协作流程

### 1. 纯日程自然语言

用户私聊 C：

```text
明天下午，大概两点开始组会，三点半结束
```

流程：

```text
User -> C
C 调 LLM 解析成 calendar.add_event
C -> A: service=calendar, action=add_event
A 写入 SQLite 或返回冲突
A -> C: calendar.result
C -> User: 汇报结果
```

实现位置：

```text
C 解析自然语言日程: bots/orchestrator/planner.py:parse_calendar_plan()
C 发给 A: bot.py:_send_orchestrator_calendar_action()
A 执行日程操作: bots/calendar/service.py:handle_calendar_request()
C 汇报结果: bots/orchestrator/planner.py:summarize_calendar_result()
```

### 2. 天气查询

用户私聊 C：

```text
这周末上海会下雨吗
```

流程：

```text
User -> C
C 调 LLM 解析地点、日期、目标
C -> B: service=weather, action=hourly_forecast
B 调 Open-Meteo geocoding + forecast
B -> C: weather.result
C -> User: 汇报降水概率和天气时段
```

实现位置：

```text
C 解析天气意图: bots/orchestrator/planner.py:parse_weather_plan()
C 发给 B: bot.py:_send_orchestrator_weather_action()
B 查询天气: bots/weather/service.py:handle_weather_request()
B 地理编码: bots/weather/service.py:_geocode()
B forecast: bots/weather/service.py:_forecast()
C 汇报天气: bots/orchestrator/planner.py:summarize_weather_results()
```

### 3. 天气感知日程安排

用户私聊 C：

```text
我在上海，这周末帮我找个不下雨的时间打球
```

流程：

```text
User -> C
C 解析: location=上海, dates=周六/周日, goal=avoid_rain, activity=打球, duration=120
C -> B: 查询周末每天的天气
B -> C: weather.result
C -> A: 查询周末每天的空闲时间
A -> C: calendar.result blocks
C -> D: 发送天气时段 + 空闲时段
D -> C: slot_matcher.result matches
C -> A: add_event 使用最佳匹配时间
A -> C: calendar.result
C -> User: 最终安排结果
```

如果用户说：

```text
明天找个时间赏雨
```

C 会把目标识别成 `prefer_rain`，D 会找降水概率较高且用户空闲的时间。

实现位置：

```text
C 判断天气类请求: bot.py:_looks_like_weather_request()
C 启动天气安排流程: bot.py:_start_orchestrator_weather_workflow()
C 推进 B/A/D/A 状态机: bot.py:_handle_weather_schedule_result()
C 构造 D 输入: bot.py:_build_slot_matcher_payload()
D 匹配共同时间段: bots/slot_matcher/service.py:handle_slot_matcher_request()
C 最终添加日程: bot.py:_send_orchestrator_calendar_action()
C 最终汇报: bot.py:_finish_weather_schedule_workflow()
```

## 已加入的细节功能

### 多 profile 运行

`.env` 可以放 `BOT_A_TOKEN` 到 `BOT_D_TOKEN`。启动时只需要传 profile：

```powershell
.\.venv\Scripts\python -m tg_agent_bot C
```

实现：

```text
读取 profile 配置: config.py:load_settings()
发现 peers: config.py:_discover_bot_usernames()
解析命令行 profile: bot.py:_profile_from_argv()
```

### bot-to-bot 结构化协议

所有 bot 间消息都包成 JSON envelope。外层结构基本固定，但不是每条消息都完全一样：`request` 没有 `correlation_id`，`ack/result` 会带 `correlation_id` 指向原 request；各服务真正不同的是 `payload`。

普通 request envelope：

```json
{
  "protocol": "tg-agent-b2b",
  "version": 1,
  "type": "request",
  "id": "...",
  "source": "@BotC",
  "target": "@BotA",
  "conversation_id": "...",
  "depth": 0,
  "max_depth": 1,
  "payload": {}
}
```

普通 ack/result envelope：

```json
{
  "protocol": "tg-agent-b2b",
  "version": 1,
  "type": "ack",
  "id": "...",
  "source": "@BotA",
  "target": "@BotC",
  "conversation_id": "...",
  "correlation_id": "原 request id",
  "depth": 1,
  "max_depth": 1,
  "payload": {}
}
```

当前 payload 类型如下。

普通 ping request：

```json
{
  "kind": "hello",
  "text": "hello"
}
```

普通 ping ack：

```json
{
  "kind": "ack",
  "received_id": "原 request id",
  "received_payload_kind": "hello"
}
```

CalendarBot request：

```json
{
  "service": "calendar",
  "action": "free_time",
  "owner_chat_id": 123456,
  "date": "2026-06-06",
  "min_duration_minutes": 120
}
```

CalendarBot result：

```json
{
  "kind": "calendar.result",
  "service": "calendar",
  "action": "free_time",
  "ok": true,
  "date": "2026-06-06",
  "min_duration_minutes": 120,
  "blocks": [
    {
      "starts_at": "2026-06-06T10:00:00+08:00",
      "ends_at": "2026-06-06T13:00:00+08:00",
      "duration_minutes": 180
    }
  ]
}
```

WeatherBot request：

```json
{
  "service": "weather",
  "action": "hourly_forecast",
  "location": "上海",
  "date": "2026-06-06",
  "country_code": "CN",
  "timezone": "Asia/Shanghai",
  "interval_hours": 3
}
```

WeatherBot result：

```json
{
  "kind": "weather.result",
  "service": "weather",
  "action": "hourly_forecast",
  "ok": true,
  "location_query": "上海",
  "location": {
    "name": "上海",
    "admin1": "上海市",
    "country": "中国",
    "country_code": "CN",
    "latitude": 31.22222,
    "longitude": 121.45806
  },
  "date": "2026-06-06",
  "timezone": "Asia/Shanghai",
  "interval_hours": 3,
  "periods": [
    {
      "starts_at": "2026-06-06T09:00",
      "ends_at": "2026-06-06T12:00",
      "max_precipitation_probability": 10,
      "precipitation_mm_sum": 0.0,
      "weather_code": 2,
      "weather": "局部多云",
      "temperature_2m_c_avg": 26.5
    }
  ],
  "source": {
    "provider": "Open-Meteo",
    "geocoding_url": "https://geocoding-api.open-meteo.com/v1/search",
    "forecast_url": "https://api.open-meteo.com/v1/forecast?..."
  }
}
```

SlotMatcherBot request：

```json
{
  "service": "slot_matcher",
  "action": "match_slots",
  "goal": "avoid_rain",
  "duration_minutes": 120,
  "rain_threshold": 30,
  "weather_periods": [
    {
      "starts_at": "2026-06-06T09:00",
      "ends_at": "2026-06-06T12:00",
      "weather": "多云",
      "max_precipitation_probability": 10
    }
  ],
  "calendar_blocks": [
    {
      "starts_at": "2026-06-06T10:00:00+08:00",
      "ends_at": "2026-06-06T13:00:00+08:00",
      "duration_minutes": 180
    }
  ]
}
```

SlotMatcherBot result：

```json
{
  "kind": "slot_matcher.result",
  "service": "slot_matcher",
  "action": "match_slots",
  "ok": true,
  "goal": "avoid_rain",
  "duration_minutes": 120,
  "rain_threshold": 30,
  "matches": [
    {
      "starts_at": "2026-06-06T10:00:00+08:00",
      "ends_at": "2026-06-06T12:00:00+08:00",
      "available_until": "2026-06-06T12:00:00+08:00",
      "duration_minutes": 120,
      "weather": "多云",
      "max_precipitation_probability": 10
    }
  ]
}
```

错误 result 通用结构：

```json
{
  "kind": "weather.result",
  "service": "weather",
  "action": "hourly_forecast",
  "ok": false,
  "error": "错误原因"
}
```

实现：

```text
构造 request: b2b.py:make_payload_request()
构造 response: b2b.py:make_response()
解析 envelope: b2b.py:parse_envelope()
防止 ACK 循环: b2b.py:should_ack()
Telegram 收包分发: bot.py:_handle_b2b_message()
```

### 防循环和去重

当前防护：

```text
ACK 不回复 ACK
每个 message id 只处理一次
普通 ACK 使用 depth/max_depth 限制
总控 workflow 由固定阶段推进，不由服务 bot 自发递归
```

实现：

```text
depth/max_depth: b2b.py:B2BEnvelope
是否自动 ACK: b2b.py:should_ack()
seen id 去重: bot.py:_handle_b2b_message()
总控 pending workflow: bot.py:_handle_orchestrator_b2b_result()
```

### 连续追问补全

用户说：

```text
这周末帮我找个不下雨的时间
```

C 会追问地点。用户只回复：

```text
上海
```

C 会把它合并回上一轮请求继续执行。

实现：

```text
保存待补全请求: bot.py:_handle_orchestrator_text()
合并“用户补充信息”: bot.py:_handle_orchestrator_text()
天气规划器理解补充信息: bots/orchestrator/planner.py:parse_weather_plan()
```

### 日程服务能力

CalendarBot 支持：

```text
list_events
events_on_day
free_time
add_event
schedule_event
delete_event
set_preference
get_preference
move_event
reschedule_event
```

自然语言例子：

```text
明天找时间打球2个小时
帮我将组会延后1小时
刚刚说错了，我不是明天打球，是后天
```

实现：

```text
统一入口: bots/calendar/service.py:handle_calendar_request()
查空闲: schedule.py:free_time_blocks()
找可安排 slot: schedule.py:pick_schedule_slot()
改日期/延后: bots/calendar/service.py:_find_single_event()
替换事件: bots/calendar/service.py:_replace_single_event()
SQLite 存储: schedule.py:ScheduleStore
```

### 天气服务能力

WeatherBot 支持中国地区指定日期的小时级天气和降水概率。

数据源：

```text
Open-Meteo Geocoding API
https://geocoding-api.open-meteo.com/v1/search

Open-Meteo Forecast API
https://api.open-meteo.com/v1/forecast
```

实现：

```text
统一入口: bots/weather/service.py:handle_weather_request()
地名转经纬度: bots/weather/service.py:_geocode()
查询小时预报: bots/weather/service.py:_forecast()
生成小时数据: bots/weather/service.py:_hourly_entries()
生成 3 小时聚合时段: bots/weather/service.py:_period_entries()
天气码中文化: bots/weather/service.py:weather_code_label()
```

### SlotMatcherBot 匹配能力

SlotMatcherBot 输入两类时间段：

```text
WeatherBot: weather_periods
CalendarBot: calendar_blocks
```

输出满足持续时间、天气偏好、日历空闲的共同时间段。

实现：

```text
统一入口: bots/slot_matcher/service.py:handle_slot_matcher_request()
avoid_rain / prefer_rain 过滤: bots/slot_matcher/service.py:handle_slot_matcher_request()
候选排序: bots/slot_matcher/service.py:_sort_key()
时间解析: bots/slot_matcher/service.py:_parse_datetime()
```

## 手动调试命令

```text
/b2b_status
/b2b_debug
/b2b_ping B hello
/b2b_calendar A {"action":"free_time","date":"2026-06-05","min_duration_minutes":120}
/b2b_weather B {"location":"北京","date":"2026-06-05"}
```

命令实现：

```text
ping: bot.py:b2b_ping()
状态: bot.py:b2b_status()
debug: bot.py:b2b_debug()
手动 CalendarBot 请求: bot.py:b2b_calendar()
手动 WeatherBot 请求: bot.py:b2b_weather()
```

## 验证

编译检查：

```powershell
.\.venv\Scripts\python -m compileall tg_agent_bot
```

# 测试
```
明天下午，大概两点开始组会，三点半结束
明天找时间打球2个小时
明天约朋友吃饭
帮我看看明天有哪些空闲时间
列一下我的日程
删除3号日程
我一般不想上午开会
刚刚说错了，我不是明天打球，是后天
帮我将组会延后1小时

这周末帮我找个下雨的时间玩水
