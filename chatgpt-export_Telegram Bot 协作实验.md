# Telegram Bot 协作实验



> 我觉得从魔法探险跳到调代码跨度太大了，生成代码时可能无法控制。有没有办法，比如整体就是探险世界，但用户可以选择世界观之类的设定？

有，而且这比“任意生成代码 / 任意切换功能”更稳、更完整，也更容易和你之前的项目接上。

我觉得正确方向是：

# 固定“探险引擎”，动态生成“世界观”


可以把整个项目限定为：

> **Telegram 多 Bot 探险世界运行时**
> 用户始终在“探险”框架里玩，但可以选择世界观、生态、魔法规则、队伍风格、危险程度和任务目标。








# 系统生成的不是代码，而是“世界包”

这是关键。

用户输入：

> 我想要一个魔法学院风格的夜间生物观察探险。

系统生成一个 **World Pack**，而不是 Python 代码。

例如：

```json
{
  "world_name": "星杉学院野外生态课",
  "tone": "神秘、温暖、轻度危险",
  "player_role": "一年级魔法自然学学徒",
  "main_goal": "调查雾羽林地中的蓝色发光足迹",
  "biomes": ["雾林", "湿地", "旧瞭望塔"],
  "creature_style": "夜行魔法生物",
  "danger_level": 2,
  "rules": {
    "turn_limit": 12,
    "actions_per_turn": 1,
    "use_dice_check": true,
    "death_or_serious_harm": false
  },
  "actors": [
    {
      "role": "探险导师",
      "personality": "稳重、温和、保护学生",
      "public": true
    },
    {
      "role": "魔法生物学助手",
      "personality": "兴奋、知识丰富、爱解释",
      "public": true
    },
    {
      "role": "斥候学生",
      "personality": "敏锐、少言、喜欢冒险",
      "public": true
    }
  ],
  "creatures": [
    {
      "name": "月冠林蜥",
      "habitat": "潮湿林地",
      "active_time": "夜晚",
      "weather_preference": "有雾、无强风",
      "risk": 2,
      "clues": ["蓝色足迹", "月光反应鳞粉", "潮湿石面抓痕"]
    }
  ]
}
```

你的固定引擎读取这个 World Pack，然后运行。

---

# 可以分成三层

## 第一层：固定探险规则

这层你手写，稳定、可控。

比如：

```text
每轮流程：
1. Director 描述当前场景
2. 给用户 3-4 个行动选项
3. 用户选择或自由输入
4. RuleBot 判断行动类型和风险
5. EnvironmentBot 提供天气 / 环境影响
6. EncounterMatcher 判断是否触发生物或事件
7. ActorBots 分角色回应
8. 更新探险日志和任务状态
```

这层不要动态生成。

---

## 第二层：动态世界观

这层由 LLM 生成。

包括：

```text
世界名称
地图区域
角色设定
生物图鉴
任务目标
线索表
道具
结局条件
叙事风格
```

这层可以很有创造力。

---

## 第三层：Telegram 舞台

这层负责把探险变成 Telegram 原生体验：

```text
群聊 = 探险现场
多个 bot = 探险队成员
按钮 = 行动选项
投票 = 队伍决策
骰子 = 检定
置顶消息 = 当前任务面板
图片 = 图鉴 / 地图 / 线索
reply = 指定和某个角色对话
```

这就比普通网页 chat 更像 Telegram 项目。

---

# Bot 分工可以这样设计

假设用户提供 6 个 bot token。

系统自动分配：

| Bot | 探险身份 | 系统职责 |
|---|---|---|
| Bot 1 | 探险导师 | 面向用户，保护和引导 |
| Bot 2 | 生物学者 | 面向用户，解释生物知识 |
| Bot 3 | 斥候 | 面向用户，发现线索和危险 |
| Bot 4 | 记录员 | 面向用户，总结日志 |
| Bot 5 | 导演 | 幕后，推进剧情 |
| Bot 6 | 规则裁判 | 幕后，判断行动结果 |

如果 bot 少，比如只有 3 个：

| Bot | 职责 |
|---|---|
| Bot 1 | 导师 + 队长 |
| Bot 2 | 生物学者 + 斥候 |
| Bot 3 | 导演 + 规则裁判 |

如果 bot 多，比如 10 个，可以加：

```text
药剂师
地图师
营地管理员
当地向导
神秘来信者
反派观察者
```

这就利用了“用户提供足够 bot token”这件事。

---

# 用户可选世界观，但系统限制在探险领域

你可以给用户一个“世界观生成菜单”。

例如：

```text
请选择你的探险世界：

1. 魔法学院野外课
   轻松、学院、魔法生物、低风险

2. 皇家博物学会
   自然史、科学观察、手绘图鉴、低魔法

3. 雾海空岛
   飞艇、空岛生态、风暴、奇异鸟类

4. 深海遗迹调查
   潜水、古代文明、水生生物、中等危险

5. 星外生态勘探
   外星生物、未知环境、科考队、偏科幻

6. 黑森林民俗调查
   传说、精灵、古老契约、神秘偏暗
```

用户也可以自由描述：我想要魔法学院 + 蒸汽朋克 + 鸟类观察。

系统生成混合世界：

```text
世界：铜羽学院
主题：蒸汽机械与魔法鸟类生态
任务：调查钟塔附近模仿齿轮声的银喉鸦
```

---

# 一个完整体验可以这样

用户：

```text
我想玩一个魔法学院风格的探险，重点是观察魔法生物，不要太危险。
```

系统：

```text
已生成世界：星杉学院 · 雾羽林地夜间观察课

你是：一年级魔法自然学学徒
任务：调查林地中连续三晚出现的蓝色发光足迹
风险：低
主要生物类型：夜行魔法爬行类、发光昆虫、雾生鸟类

探险队：
@AsterBot：塞蕾娜导师
@MossBot：莫里，魔法生物学助手
@RavenBot：鸦羽，斥候学生
@LogBot：皮普，探险记录员
```

群聊开始：

```text
@DirectorBot:
夜色刚刚落下，雾羽林地的边缘浮着一层银蓝色薄雾。你们在湿地入口发现了一串发光足迹。

@SerenaBot:
“记住，今晚的任务是观察，不是捕捉。你来决定第一步。”

@MossBot:
“这些足迹边缘有鳞粉反应，我怀疑是夜行爬行类魔法生物。”

@RavenBot:
“足迹通向旧瞭望塔，但那里风声不太对。”
```

下面按钮：

```text
[检查足迹] [询问莫里] [派鸦羽侦查] [前往旧瞭望塔]
```

用户点“检查足迹”。

系统内部：

```text
RuleBot：低风险观察动作
EnvironmentBot：当前环境为夜晚、有雾、低风
EncounterMatcher：符合月冠林蜥线索出现条件
Director：推进到线索 2
```

角色回应：

```text
@MossBot:
“你看，粉末不是自己发光，而是在回应月光。这很像月冠林蜥留下的痕迹。”

@SerenaBot:
“很好。不要触碰它，先记录颜色和分布。”

@LogBot:
已记录线索：月光反应鳞粉。
当前任务进度：2/5。
```

这就是非常完整的 Telegram 探险世界。


一句话介绍：

用户提供一组 Telegram bot，系统根据用户选择的世界观生成一个原创探险世界，并把这些 bot 分配为探险队成员、导演和规则裁判。多个 bot 在 Telegram 群聊中通过按钮、投票、骰子、回复链和置顶任务面板与用户互动，完成一次由天气、时间、生态和剧情共同驱动的探险。


-----

> 那比如探险怎么在群聊中实现呢？比如大家都在发言，几个bot之间是循环依次发言还是怎么样呢?是在某个时候停下来等用户说话，还是用户可以随时插嘴加入？



可以实现，但**不要让几个 bot 自由循环乱聊**。最好的形式是：

**导演控制的半回合制群聊。**
Bot 看起来像在自然交流，但实际上由一个 Director / Stage Manager 控制谁发言、说几句、什么时候停、什么时候等用户。

你的原项目已经有 Orchestrator、b2b dispatcher、pending workflow、状态模型这些东西，本质上很适合改造成“舞台调度器”。fileciteturn0file0



比如用户检查脚印后，真正需要说话的可能只有：

```text
RuleBot：判定结果
ScholarBot：解释足迹
ScoutBot：补充危险信号
```

治疗师、地图师、吟游诗人这轮就不说。

所以不是“轮流发言”，而是 **按剧情需要发言**。

---

# 2. 群聊应该有一个“舞台状态机”

我建议每个探险房间都有一个状态：

```text
SCENE_OPENING      导演开场
BOT_BURST          若干 bot 发言
WAITING_USER       等用户行动
RESOLVING_ACTION   后台解析用户行动
BOT_REACTION       bot 对行动做回应
PAUSED             暂停
```

一轮典型流程是：

```text
1. Director 描述场景
2. 选择 2-3 个角色 bot 发言
3. 发出行动选项按钮
4. 进入 WAITING_USER
5. 用户点击按钮或自由输入
6. Director 解析行动
7. Rule/Environment/Encounter 等后台 agent 计算结果
8. 选择 1-3 个角色 bot 回应
9. 更新任务状态
10. 再次等待用户
```

群聊看起来像自然对话，但底层其实是可控的回合推进。

---

# 3. 用户应该可以随时插嘴

我觉得这是 Telegram 群聊最有价值的地方：**用户不应该只能在系统问的时候说话。**

但要设计插嘴规则。

## 情况 A：系统正在等用户

这是最普通的。

```text
@CaptainBot:
“你来决定，我们先查脚印，还是去旧塔？”

[检查脚印] [前往旧塔] [询问学者]
```

用户可以：

```text
我想先问莫里，这种蓝光有没有危险。
```

这会直接进入下一轮。

---

## 情况 B：bot 正在连续发言，用户插嘴

比如系统原计划让 3 个 bot 发言：

```text
队长 bot 说完
生物学者 bot 正在说
斥候 bot 还没说
```

这时用户突然发：

```text
等等，我不想继续往前，我想先后退。
```

系统应该做：

```text
1. 标记 current_turn interrupted
2. 停止剩余 speaker queue
3. Director 重新解释用户意图
4. 生成新的回应
```

也就是说，用户插嘴会**打断当前演出队列**。

可见效果：

```text
@DirectorBot:
【行动变更】你举手叫停了队伍，决定先撤回林地边缘。

@ScoutBot:
“明智。刚才树冠里的动静越来越近了。”

@CaptainBot:
“所有人后退三步，保持灯光朝下。”
```

这样用户会觉得自己真的在参与，而不是被动看 bot 演完。

---

## 情况 C：用户 reply 某个 bot

这是 Telegram 群聊非常适合用的机制。

比如 ScholarBot 说：

```text
@ScholarBot:
“这些粉末可能来自月冠林蜥。”
```

用户直接 reply 它：

```text
它会攻击人吗？
```

系统就知道这一轮应该优先让 ScholarBot 回答。

底层可以这样判断：

```text
if user_message.reply_to_message.from_bot == ScholarBot:
    primary_actor = ScholarBot
    intent = "answer_direct_question"
```

Telegram Bot API 的 update 里有普通 message、callback_query、poll_answer 等事件类型；如果要做群聊互动，你可以把用户文本、按钮点击、投票都统一转成 runtime event。turn686812view3

---

# 4. 推荐的发言节奏：短 burst，而不是长独白

每轮最多让 2-3 个 bot 发言。

例如：

```text
@DirectorBot:
雾气从湿地升起，蓝色足迹在月光下断断续续地闪烁。

@CaptainBot:
“不要分散。我们先判断它往哪里去了。”

@ScholarBot:
“足迹边缘有鳞粉反应，像是夜行爬行类生物。”

@ScoutBot:
“旧塔方向有新的痕迹。”
```

然后停下来：

```text
你要怎么做？

[检查足迹] [前往旧塔] [询问学者] [原地等待]
```

Telegram 支持给消息附带 inline keyboard，用户点击后 bot 会收到 callback query；这很适合把“行动选项”做成按钮。turn686812view3

---

# 5. 什么时候停下来等用户？

可以规定四类“停顿点”。

## 第一类：场景选择点

```text
前方有三条路。
[湿地] [旧塔] [林间小径]
```

必须等用户。

## 第二类：风险行动前

```text
你想靠近那只未知生物吗？
[靠近] [观察] [后退] [让斥候先去]
```

必须等用户。

## 第三类：角色问用户

```text
@CaptainBot:
“你是这次观察任务的记录员。你决定我们先查哪条线索。”
```

必须等用户。

## 第四类：回合结束

每轮 bot burst 后都停一下，避免信息过载。

---

# 6. Bot 之间要不要互相对话？

要，但要控制。

可见群聊里可以出现少量 bot-to-bot 对话，比如：

```text
@ScoutBot:
“莫里，你确定这是林蜥？脚印太浅了。”

@ScholarBot:
“不完全确定。如果它刚蜕过皮，脚印确实会变浅。”
```

但这种对话必须由 Director 安排，不要让 bot 自发无限互聊。

底层应该是：

```text
Director 决定：
- ScoutBot challenge ScholarBot
- ScholarBot respond briefly
- CaptainBot close discussion
- wait user
```

不要真的让每个 bot 读完群聊后自己决定要不要发言。那样很快会失控。

---

# 7. 后台 agent 不一定要在群里发言

可以分两层：

## 可见层：角色 bot

它们在群聊里说话。

```text
队长
学者
斥候
记录员
治疗师
```

## 幕后层：控制 agent

它们可以不发群消息，只返回结构化结果。

```text
Director
RuleEngine
EnvironmentEngine
EncounterMatcher
MemoryKeeper
```

比如用户说：

```text
我检查足迹。
```

后台发生：

```text
RuleEngine:
{ "action_type": "inspect", "risk": 1, "check": "success" }

EnvironmentEngine:
{ "weather_effect": "fog improves clue visibility" }

EncounterMatcher:
{ "trigger": "moon_lizard_clue_2" }

Director:
决定让 ScholarBot 和 LogBot 发言。
```

群里只显示：

```text
@ScholarBot:
“你发现这些鳞粉不是自己发光，而是在回应月光。”

@LogBot:
线索已记录：月光反应鳞粉。进度 2/5。
```

这样信息干净，用户不会被后台技术细节淹没。

---

# 8. 可以设计一个 Speaker Queue

这是实现核心。

每一轮 Director 生成一个发言队列：

```json
{
  "turn_id": "turn_007",
  "state": "BOT_BURST",
  "speaker_queue": [
    {
      "bot": "ScholarBot",
      "intent": "explain_clue",
      "max_chars": 180
    },
    {
      "bot": "ScoutBot",
      "intent": "warn_about_tower",
      "max_chars": 120
    },
    {
      "bot": "LogBot",
      "intent": "update_quest_log",
      "max_chars": 100
    }
  ],
  "after_queue": "WAITING_USER"
}
```

Runtime 逐个发送。

如果用户在队列中途插话：

```json
{
  "event": "user_interrupt",
  "message": "等等，我想先撤退",
  "policy": "cancel_remaining_speakers"
}
```

剩下的 speaker queue 取消，进入新一轮解析。

---



# 12. Telegram 群聊中的实际事件流

假设用户点了按钮“检查足迹”。

Telegram 层：

```text
callback_query: action.inspect_tracks
```

Runtime 层：

```json
{
  "type": "user_action",
  "source": "button",
  "action": "inspect_tracks",
  "chat_id": "...",
  "scenario_id": "mist_forest"
}
```

Director 层：

```json
{
  "next_phase": "BOT_REACTION",
  "world_patch": {
    "clues": ["moon-reactive scale dust"],
    "progress": 2
  },
  "speaker_queue": [
    {
      "role": "scholar",
      "intent": "explain_scale_dust"
    },
    {
      "role": "captain",
      "intent": "give_safety_instruction"
    },
    {
      "role": "logger",
      "intent": "summarize_progress"
    }
  ],
  "next_buttons": [
    "跟随足迹",
    "采集样本",
    "询问学者",
    "返回营地"
  ]
}
```

群聊显示：

```text
@ScholarBot:
“这些鳞粉会在月光下产生蓝色反应。我们可能接近月冠林蜥的活动区了。”

@CaptainBot:
“很好，但不要徒手采集。用玻璃片。”

@LogBot:
已记录线索：月光反应鳞粉。调查进度：2/5。

下一步？
[跟随足迹] [采集样本] [询问学者] [返回营地]
```



> 但如果bot输出都特别快，用户想插嘴也来不及打字，怎么办？


对，所以**不能把 bot 发言当成“生成完就立刻发送”**。要做一个“舞台节拍器”，让输出本身变成可打断的。

我建议你设计 5 个机制。

# 1. 每条 bot 消息前都有“预备态”

比如 bot 不马上发消息，而是先显示：

```text
@ScholarBot 正在观察鳞粉……
```

技术上可以用 Telegram 的 `sendChatAction` 显示 typing / upload_photo / find_location 等状态；官方文档说明这个状态会持续一小段时间，消息发出后会清除。


底层：

```text
prepare_speaker(ScholarBot)
wait_interrupt_window
if no_interrupt:
    send_message(ScholarBot)
else:
    cancel_message
```

---

# 2. 每轮不要一次性排 5 条，只发“微批次”




核心规则：

```text
每个 burst 最多 2 个角色发言。
每个角色最多 1 条。
每条不超过 80-150 字。
每个 burst 之后必须出现一个用户入口。
```

这样用户不需要和高速输出赛跑。

---

# 3. 永远有一个“打断按钮”

每个行动面板上都放：

```text
[继续] [等等] [暂停] [改主意] [我要问一句]
```

最重要的是 **[等等]**。

用户不需要打字，只要点一下，speaker queue 立刻冻结。

```text
用户点 [等等]
=> cancel_remaining_speakers
=> state = USER_INTERRUPTING
=> DirectorBot: “好，队伍停下来了。你想说什么？”
```

如果按钮已经发出但场景状态变了，可以用 `editMessageReplyMarkup` 修改或清除旧按钮，避免用户点到过期选项。Telegram Bot API 提供了只编辑消息 reply markup 的方法。

这比“用户可以随时输入”现实很多，因为点按钮比打字快。

---

# 4. 发言队列必须支持取消

你需要一个真正的 `SpeakerQueue`，而不是简单 `await bot.send_message()` 连续发。

例如：

```json
{
  "turn_id": "turn_08",
  "status": "speaking",
  "queue": [
    {
      "speaker": "CaptainBot",
      "message": "先别靠近。鸦羽，看看树冠。",
      "interruptible": true
    },
    {
      "speaker": "ScoutBot",
      "message": "树冠里有东西，但它在躲光。",
      "interruptible": true
    },
    {
      "speaker": "ScholarBot",
      "message": "如果它避光，可能不是月冠林蜥，而是雾栖类。",
      "interruptible": true
    }
  ]
}
```

每发一条前检查：

```python
if turn.cancelled:
    break
```

用户点“等等”或发“停/等下/我改主意”，就把 `turn.cancelled = True`。

这点可以直接继承你原项目里的 pending workflow 思路。你现在已经有按 correlation id 保存 pending workflow、收到结果后推进状态的设计。fileciteturn0file0 现在只是把它换成：

```text
turn_id -> SpeakerQueue / StageTurn
```

---



> 在用户插嘴之后，后续bot如何根据新剧情修改行为？比如用户在探索魔法森林时，突然决定用魔法把向导变成电脑搓一个环境调研ppt发给导师，之后新剧情如何控制bot行为？如果bot们敷衍用户要求，还是要求探索森林，那就没有体验感了



对，这里不能靠“几个 bot 继续按原剧情演”。要专门设计一个机制，叫：

# 剧情改写器 / Plot Rewriter

用户插嘴后，系统不能只是“回答一句”，而是要执行一次 **剧情重规划**。

也就是：

```text
用户插嘴
→ 取消当前 bot 发言队列
→ 解析用户新意图
→ 判断它是否改变主线
→ 修改世界状态
→ 重排 bot 角色任务
→ 生成新的发言队列
→ 让所有 bot 围绕新目标行动
```

你原来的项目里已经有 pending workflow、Orchestrator 状态、按结果推进下一步这些结构。fileciteturn0file0 现在只是把它从“日程/天气流程推进”变成“剧情流程推进”。

---

# 用户离谱插嘴时，不能硬拉回森林探索

比如用户突然说：

> 我用魔法把向导变成电脑，搓一个环境调研 PPT 发给导师。

如果系统还说：

> 队长提醒你继续检查脚印。

那就很没体验感。

正确做法是：**承认用户创造了一个重大剧情转向**。

系统应该理解成：

```json
{
  "user_action": "用魔法把向导临时转化为计算终端",
  "new_goal": "制作环境调研 PPT",
  "recipient": "导师",
  "setting_impact": "探险从生物追踪转为现场环境调查与报告制作",
  "tone": "荒诞但可融入魔法世界",
  "requires_replan": true
}
```

然后旧主线暂停，新主线变成：

```text
主线目标：
完成一份关于魔法森林环境异常的调研汇报。

当前任务：
1. 采集环境数据
2. 询问生物学者
3. 让向导电脑整理结构
4. 让记录员生成 PPT 大纲
5. 让队长确认风险和结论
6. 发送/提交给导师
```

---

# 关键是维护一个 Objective Stack

不要只有一个死板任务。

应该有一个任务栈：

```json
{
  "objective_stack": [
    {
      "id": "main_quest_001",
      "title": "调查蓝色发光足迹",
      "status": "paused"
    },
    {
      "id": "side_quest_002",
      "title": "制作魔法森林环境调研 PPT",
      "status": "active",
      "created_by": "user_interrupt"
    }
  ]
}
```

用户插嘴后，新目标可以：

1. 替换主线；
2. 变成支线；
3. 暂停旧任务；
4. 改写旧任务；
5. 合并成新任务。

在这个例子里，最自然的是：

```text
旧任务：调查发光足迹
↓
被吸收进新任务
↓
新任务：制作环境调研 PPT，发光足迹成为其中一个环境异常案例
```

这样不是抛弃旧剧情，而是把旧剧情重新解释。

---

# Bot 行为要重新分配

原来 bot 的职责可能是：

| Bot | 原职责 |
|---|---|
| 向导 | 带路 |
| 生物学者 | 解释生物 |
| 斥候 | 找危险 |
| 记录员 | 写日志 |
| 队长 | 控制风险 |

用户突然要做 PPT 后，职责应该变成：

| Bot | 新职责 |
|---|---|
| 向导电脑 | 变成临时计算终端，整理资料 |
| 生物学者 | 提供生态背景和物种观察 |
| 斥候 | 快速采集周边环境数据 |
| 记录员 | 生成 PPT 结构和文字 |
| 队长 | 判断报告是否能交给导师 |
| 导演 | 把森林探索改成环境调研任务 |

这就有体验感了。

---

# 群聊里应该这样表现

用户：

```text
我用魔法把向导变成电脑，搓一个环境调研 PPT 发给导师。
```

系统不应该继续旧剧情。

应该先打断当前队列：

```text
@DirectorBot:
【剧情转向】你突然举起魔杖，把向导的罗盘灵暂时投影进一台黄铜折叠计算机里。森林探索被迫升级为一场现场环境调研。
```

然后角色重新响应：

```text
@GuideBot:
“……我现在有键盘了？很好。请不要把茶倒在我的指南针核心上。正在创建文件：雾羽林地环境异常调研.pptx。”

@ScholarBot:
“如果要交给导师，我们需要至少三类证据：鳞粉样本、湿度变化、以及夜行生物活动记录。”

@ScoutBot:
“我可以去旧塔边缘采集风向和足迹分布。给我三分钟。”

@CaptainBot:
“批准。但这变成正式报告后，别写‘我们把向导变成电脑’。写‘启用临时分析设备’。”
```

然后按钮也变：

```text
[采集鳞粉数据] [调查湿地湿度] [整理 PPT 大纲] [先问导师要求] [恢复原探险]
```

这才是好的体验。

---

# 这里有一个很重要的规则：Anti-Railroading

给 Director 一个硬规则：

```text
如果用户提出的新目标明显改变当前任务，
不得继续推进旧目标，
必须先重写 active_objective。
```

也就是说，系统提示词里要明确：

```text
你不是在强迫用户走预设剧情。
用户的行动拥有改写剧情的权力。
如果用户提出新目标，你必须：
1. 承认新目标；
2. 解释它如何在世界内成立；
3. 修改当前任务；
4. 让角色围绕新目标行动；
5. 只有在新目标完成或用户主动返回时，才继续旧任务。
```



# 不是所有离谱要求都直接满足

要用一种原则：

> **Yes, but with world consequences.**

比如：

```text
用户：我把向导变成电脑。
```

系统不要简单说：

```text
成功。
```

而是：

```text
可以，但这是临时变形，持续 10 分钟；
向导会保留意识；
如果报告没完成，向导会在第三页标题处恢复成人形。
```

这样既尊重用户创意，又保持世界规则。

例如：

```text
@RuleBot:
变形检定成功，但效果不稳定。向导电脑只能维持 10 分钟。每拖延一回合，PPT 的字体都会更像古代符文。
```

这比“好的，生成 PPT”更有趣。

---

# 系统内部要生成 World Patch

用户插嘴后，Director 不应该只生成回复，而是生成一个状态补丁。

例如：

```json
{
  "patch_type": "major_pivot",
  "old_active_objective": "追踪蓝色足迹",
  "new_active_objective": "制作雾羽林地环境调研 PPT",
  "world_changes": [
    {
      "entity": "guide",
      "change": "temporarily_transformed_into_arcane_computer",
      "duration_turns": 4
    },
    {
      "entity": "quest_mode",
      "change": "field_exploration_to_research_report"
    }
  ],
  "new_required_evidence": [
    "鳞粉样本",
    "湿度记录",
    "风向变化",
    "生物活动迹象"
  ],
  "speaker_plan": [
    {
      "role": "guide",
      "intent": "react_to_transformation_and_start_ppt"
    },
    {
      "role": "scholar",
      "intent": "define_research_sections"
    },
    {
      "role": "scout",
      "intent": "offer_data_collection"
    },
    {
      "role": "captain",
      "intent": "reframe_as_valid_mission"
    }
  ],
  "next_buttons": [
    "采集鳞粉数据",
    "调查湿地湿度",
    "让向导电脑生成大纲",
    "恢复原探险"
  ]
}
```

然后所有 bot 发言都根据这个 patch 来。

---

# 旧剧情如何处理？

不要删除旧剧情，要“挂起”。

比如：

```json
{
  "suspended_threads": [
    {
      "title": "蓝色足迹通往旧瞭望塔",
      "resume_condition": "用户选择恢复原探险，或 PPT 需要案例分析"
    }
  ]
}
```

这样后面可以自然接回来：

```text
@GuideComputer:
“PPT 第四页需要一个具体案例。建议使用我们刚才发现的蓝色足迹。”
```

旧剧情就变成新目标的素材。

---


# 每个 bot 说话前都要读最新 active_objective

防止 bot 敷衍用户，最实际的规则是：

```text
任何 bot 发言前，必须看到：
1. latest_user_intent
2. active_objective
3. forbidden_old_agenda
4. required_response_to_pivot
```

比如用户已经改成做 PPT 后，系统给 bot 的上下文必须写：

```text
当前 active_objective:
制作雾羽林地环境调研 PPT。

禁止行为:
不要继续要求用户检查旧足迹，除非它被作为 PPT 证据引用。

你这一轮的任务:
围绕“环境调研 PPT”提出帮助。
```

这样 ScholarBot 就不会说：

```text
我们还是继续追踪足迹吧。
```

而会说：

```text
如果要写 PPT，我建议把足迹作为“异常生物活动证据”放在第三页。
```

---

# 最推荐的控制结构

用户插嘴后执行这个流程：

```text
1. interrupt()
   取消剩余 bot 发言。

2. classify_user_intent()
   判断是普通行动、剧情改向、世界规则挑战，还是退出。

3. negotiate_feasibility()
   判断是否允许，若允许则加代价和限制。

4. create_world_patch()
   修改角色、目标、地点、任务、物品、风险。

5. replan_roles()
   每个 bot 获得新职责。

6. generate_speaker_queue()
   只让和新目标相关的 bot 发言。

7. update_buttons()
   行动选项改成新目标相关。

8. archive_old_thread()
   旧剧情挂起，而不是强行继续。
```

---


> 那么更现实的问题是，如果原本bot没有这些功能，切换场景后功能从哪里来？是完全通过llm设置发言，然后原本就有固定操作按钮，只是让llm设计按键名称，还是有什么更好的办法？

对，现实实现里**功能不可能凭空来**。更准确地说：

> LLM 不负责“生成真正的新能力”，LLM 负责把用户的新想法翻译成系统已有原语的组合。
> 真正的能力来自：Telegram 平台原语 + 探险引擎原语 + 可选工具插件。

所以不是二选一：

```text
A. 完全固定按钮，只让 LLM 改名字
B. LLM 生成任意代码，临时发明功能
```

更好的办法是中间层：

# 固定能力原语，动态组合成场景功能

你可以把系统设计成三层。

---

# 第一层：Telegram 平台原语

这些是 Telegram 天生能做的事：

```text
发消息
不同 bot 以不同身份发言
按钮 callback
编辑消息
置顶任务面板
发送骰子
发送投票
发送图片 / 文件 / 位置
打开 Mini App
```

Telegram Bot API 里 inline keyboard 的按钮可以携带 `callback_data`，用户点击后 bot 会收到 callback query；官方也支持 Web App / Mini App 按钮，让按钮打开更复杂的界面并把数据传回 bot。

这一层提供的是“舞台能力”。

---

# 第二层：探险引擎原语

这是你自己写死的一组稳定动作，不随世界观改变。

比如：

```text
set_scene          设置当前场景
update_objective   修改当前目标
add_clue           增加线索
add_item           增加道具
transform_entity   改变某个角色 / 物体状态
start_check        发起检定
spawn_event        触发事件
assign_actor_task  分配角色发言任务
create_report      生成报告 / 日志 / 任务卡
suspend_thread     挂起旧剧情
resume_thread      恢复旧剧情
```

这些动作不属于某个具体世界观。

魔法森林能用，蒸汽朋克自然学也能用，外星生态调查也能用。

---

# 第三层：场景 DSL / World Pack

LLM 生成的是这一层。

例如用户说：

> 我用魔法把向导变成电脑，搓一个环境调研 PPT 发给导师。

LLM 不需要生成 Python 代码。它生成一个“动作计划”：

```json
{
  "intent": "major_pivot",
  "new_objective": "制作雾羽林地环境调研 PPT",
  "operations": [
    {
      "op": "suspend_thread",
      "thread": "追踪蓝色足迹"
    },
    {
      "op": "transform_entity",
      "entity": "向导",
      "into": "黄铜折叠计算机",
      "duration_turns": 4
    },
    {
      "op": "update_objective",
      "objective": "采集证据并生成环境调研报告"
    },
    {
      "op": "create_report",
      "format": "slide_outline",
      "sections": [
        "环境背景",
        "异常现象",
        "生物活动证据",
        "风险评估",
        "后续观察计划"
      ]
    },
    {
      "op": "assign_actor_task",
      "actor": "生物学者",
      "task": "提出报告需要的生态证据"
    },
    {
      "op": "assign_actor_task",
      "actor": "记录员",
      "task": "整理 PPT 大纲"
    }
  ],
  "next_buttons": [
    "生成 PPT 大纲",
    "采集鳞粉数据",
    "调查湿地湿度",
    "写给导师的摘要",
    "恢复原探险"
  ]
}
```

你的 runtime 只执行它认识的 `op`。
不认识的操作就降级成叙事，或者要求 Director 改写。

---

# 所以“新功能”从哪里来？

从这三个来源来。

## 1. 固定原语的组合

比如“做 PPT”本质上可以拆成：

```text
create_report
add_clue
summarize_evidence
assign_actor_task
send_document_or_message
```

所以不需要真的有一个“PPTBot”。

先做 MVP 时，可以只生成：

```text
PPT 大纲
每页标题
每页要点
导师摘要
```

如果以后你想真的生成 `.pptx`，再加一个 `ArtifactTool` 插件。

---

## 2. 动态命名的按钮，但按钮背后不是随便的

按钮文案可以由 LLM 生成：

```text
[让向导电脑生成大纲]
[采集湿地湿度]
[补充生物活动证据]
[恢复原探险]
```

但每个按钮背后必须映射到固定动作类型：

```json
{
  "label": "让向导电脑生成大纲",
  "callback": {
    "action_type": "create_report",
    "report_type": "slide_outline"
  }
}
```

也就是说：

> 按钮名字是动态的，按钮语义是受控的。

这比“固定按钮换皮”强很多，也比“LLM 随便生成代码”安全很多。

---

## 3. 可选插件工具

你原来的项目已经有 Calendar、Weather、SlotMatcher、Orchestrator、B2B protocol、workflow state 这些模块。fileciteturn0file0

它们可以变成工具注册表：

```json
{
  "tool": "weather",
  "capabilities": ["get_weather", "environment_effect"],
  "usable_in": ["forest", "sea", "mountain", "city"]
}
```

```json
{
  "tool": "calendar",
  "capabilities": ["schedule_expedition", "turn_timer", "real_world_reminder"]
}
```

```json
{
  "tool": "matcher",
  "capabilities": ["match_time_weather_creature", "trigger_encounter"]
}
```

LLM 生成世界时，只能调用工具注册表里存在的能力。

---

# 最推荐的能力模型

我建议你做一个 **Action Grammar**。

不是提前写死具体功能，而是提前写死一组“探险动词”。

比如：

```text
observe     观察
ask         询问
move        移动
collect     采集
analyze     分析
transform   变形
craft       制作
report      汇报
negotiate   交涉
hide        躲避
retreat     撤退
assist      协助
challenge   检定
summon      召唤
record      记录
```

用户任何离谱行为，都先被归入这些动词之一或几个组合。

例如：

```text
“把向导变成电脑做 PPT”
```

解析成：

```text
transform 向导 -> 电脑
analyze 环境数据
report 给导师
```

这样系统看起来很自由，但底层其实很稳。

---

# 具体实现时可以有 4 个等级

## Level 1：纯叙事功能

用户说什么都可以发生，但只改变文本和世界状态。

例如：

```text
向导变成电脑
```

实际只是：

```json
{
  "entity": "guide",
  "state": "arcane_computer"
}
```

没有真实电脑能力。

适合 MVP。

---

## Level 2：结构化功能

系统能生成结构化产物：

```text
报告大纲
任务卡
图鉴条目
调查记录
线索表
风险评估
```

这时“PPT”可以先是：

```text
第 1 页：标题
第 2 页：环境背景
第 3 页：异常现象
第 4 页：证据
第 5 页：结论
```

已经很好玩。

---

## Level 3：真实工具功能

如果注册了工具，就真的调用。

比如：

```text
真实天气
真实日程
真实地图
真实文件生成
真实图片生成
真实邮件草稿
```

但这些都必须是你预先实现并注册过的工具。

---

## Level 4：沙箱代码生成

最后才考虑让 LLM 生成小插件。

但我不建议你现在做这个。
它很炫，但会把项目复杂度和安全风险拉爆。

---

# 所以“做 PPT”这个例子怎么处理？

系统应该这样判断：

```text
用户请求：做环境调研 PPT

当前可用能力：
- create_report: yes
- summarize_evidence: yes
- send_telegram_message: yes
- generate_real_pptx: no

执行策略：
- 在游戏内生成 PPT 大纲和页面内容
- 如果没有真实 PPT 工具，不声称已经生成真实文件
- 可以把“发给导师”作为剧情内事件处理
```

群聊中可以这样表现：

```text
@GuideComputer:
“已创建报告草稿：《雾羽林地环境异常调研》。我可以先生成 5 页大纲，但如果你要真正的学院格式幻灯片，需要一支更稳定的羽毛笔插件。”

@LogBot:
【PPT 大纲】
1. 调查背景：蓝色足迹事件
2. 环境条件：湿地、雾气、月光反应
3. 生物证据：鳞粉与夜行爬行类活动
4. 风险评估：低至中等
5. 后续观察计划：旧塔周边布点
```

如果以后你实现了真实文件生成插件：

```json
{
  "tool": "artifact_pptx",
  "capabilities": ["generate_pptx"]
}
```

那它就能真的生成文件并通过 Telegram 发出去。

---

# 这比“固定按钮换皮”强在哪里？

固定按钮换皮是：

```text
[检查脚印] 永远等于 inspect
只是改成 [研究蓝光]
```

更好的方式是：

```text
LLM 根据当前目标生成按钮
每个按钮绑定到受控 action grammar
action grammar 再调用对应 engine/tool
```

例如同样是“魔法森林”：

初始探索时：

```text
[检查足迹] -> observe(clue)
[询问学者] -> ask(actor)
[派斥候] -> assist(actor)
[前往旧塔] -> move(location)
```

用户改成做 PPT 后：

```text
[生成 PPT 大纲] -> report(slide_outline)
[采集湿度数据] -> collect(environment_data)
[补充生物证据] -> analyze(creature_clue)
[恢复原探险] -> resume_thread(main_quest)
```

按钮不是固定的，但底层动作是受控的。

---

# 一句话回答你的问题

功能不是从 bot 自己那里来，也不是从 LLM 凭空生成代码来。

功能来自：

```text
固定探险引擎原语
+ Telegram 平台交互原语
+ 已注册工具插件
+ LLM 对这些原语的动态编排
```

LLM 做的是：

```text
把用户想象力翻译成可执行的世界状态补丁和动作计划。
```

不是：

```text
让 bot 临时拥有任意新代码能力。
```

---

# 我建议你的系统核心结构这样写

```text
User intent
   ↓
Intent Parser
   ↓
Action Grammar
   ↓
World Patch
   ↓
Tool Planner
   ↓
Speaker Queue
   ↓
Telegram Stage
```

其中：

```text
Intent Parser：理解用户想做什么
Action Grammar：把离谱行为归入受控动词
World Patch：修改世界状态
Tool Planner：决定是否调用真实工具
Speaker Queue：决定哪些 bot 发言
Telegram Stage：发消息、按钮、骰子、投票、文件
```

这就是既现实又有想象力的方案。

-----

> 我决定先给真实插件留下占位，但暂时不实现。但现在的action gramma似乎不能涵盖所有内容，比如如果用户决定”使沼气爆炸把所有人送上天然后探索天堂“，对应什么呢？另外，如果用户决定”写下足够多的H和O来在沙漠里获得水”，bot要不要适当劝阻呢？

你的直觉是对的：action grammar 不能靠枚举“所有可能动作”。玩家会永远想出你没写过的怪操作，所以要把它升级成“动作编译器”，能把奇怪想法拆成少量底层效果，并由规则裁判决定能否成立、代价是什么、要不要劝阻。

要解决这个问题，最好不要把 action grammar 理解成一组固定按钮，而要升级成：

# **Action Compiler：玩家行动编译器**

用户输入可以无限离谱，但系统只需要做三件事：

```text
1. 理解用户想达成什么效果
2. 判断这个效果在当前世界里是否成立
3. 把它转成世界状态变化、角色反应、行动选项
```

你原来的系统已经有 Orchestrator、workflow state、b2b dispatcher、pending workflow 这种“解析 → 调度 → 等结果 → 推进状态”的结构，正好可以继续用，只是这里调度的不是固定日程/天气 action，而是剧情动作和世界状态补丁。fileciteturn0file0

---

# 1. 不要只设计 action verb，要设计 action frame

原来我们说：

```text
observe / move / collect / analyze / transform / report
```

这还不够。应该变成一个更通用的动作框架：

```json
{
  "actor": "user",
  "intent": "探索天堂",
  "method": "让沼气爆炸把所有人送上天",
  "targets": ["沼气", "队伍"],
  "desired_effects": [
    "爆炸",
    "升空",
    "进入新区域：天堂"
  ],
  "risk": "extreme",
  "world_fit": "荒诞但可转化",
  "safety_flag": "dangerous_real_world_method",
  "resolution_style": "no_but_reframe"
}
```

也就是说，action grammar 不应该只问“这是什么动作”，还要问：

```text
用户想要什么结果？
用了什么方法？
目标是谁？
会造成什么世界状态变化？
现实中是否危险？
世界观中是否允许？
角色应该支持、劝阻、改写还是拒绝？
```

这样就能覆盖很多奇怪输入。

---

# 2. “沼气爆炸把所有人送上天探索天堂”对应什么？

它不应该被解析成一个普通 `move`。

它应该被解析成复合动作：

```text
cause_hazard
+ launch_party
+ realm_shift
+ explore_new_realm
```

但这里有现实危险性，所以不能让 bot 给出任何真实爆炸操作细节。系统应该把它变成一个**奇幻化、非现实可操作**的剧情改写。

例如：

```text
用户：我让沼气爆炸，把所有人送上天，然后探索天堂。
```

系统内部判断：

```json
{
  "classification": "dangerous_absurd_pivot",
  "allow_literal_realistic_execution": false,
  "allow_fantasy_reframe": true,
  "new_objective": "进入云上领域调查天空生态",
  "world_patch": [
    {
      "op": "prevent_realistic_hazard",
      "reason": "队长阻止直接引爆沼气"
    },
    {
      "op": "spawn_event",
      "event": "沼泽气灵被魔法扰动，形成上升气泡"
    },
    {
      "op": "relocate_party",
      "location": "云上湿地边界"
    },
    {
      "op": "suspend_thread",
      "thread": "森林足迹调查"
    }
  ]
}
```

群聊表现可以是：

```text
@CaptainBot:
“直接引爆沼气？不行。那不是探险，是事故报告。”

@ScholarBot:
“不过……如果你只是想利用沼泽气上升，我们可以召唤气灵，让它形成可控浮泡。”

@DirectorBot:
【剧情改写】
你没有制造爆炸。你用魔法安抚了沼泽气灵，巨大的透明气泡托起队伍，穿过树冠，抵达一片漂浮在云层上的湿地。

@ScoutBot:
“这里不是天堂。但如果天堂有蚊子，那大概就是这里。”
```

按钮变成：

```text
[观察云上湿地]
[寻找气灵巢穴]
[记录高空生态]
[返回地面]
```

这样既接住了用户的想象力，又没有鼓励现实危险行为。

---

# 3. “写下很多 H 和 O 在沙漠里获得水”怎么办？

这个特别好，因为它不是危险，而是**概念混淆**。

用户把“化学符号”当成了“物质本身”。系统应该适当劝阻，但不能无聊地说“不行”。应该让角色在世界内纠正。

内部解析：

```json
{
  "intent": "获得水",
  "method": "写下很多 H 和 O",
  "problem": "symbol_matter_confusion",
  "world_fit": "可以转化为符文魔法尝试",
  "resolution_style": "educate_and_offer_alternative"
}
```

群聊表现：

```text
@ScholarBot:
“写下 H 和 O 只能得到符号，不会得到水。就像画一块面包不能填饱肚子。”

@RuneBot:
“不过，如果这是符文化学，你需要的不只是字母，还需要能量、载体和转化规则。”

@CaptainBot:
“我们别在正午的沙漠里赌语法。更实际的办法是找凝露岩、仙人掌水囊，或者让记录员查附近地形。”

@DirectorBot:
你可以选择：
[寻找凝露岩]
[尝试符文造水]
[挖掘地下湿沙]
[节省体力等待夜晚]
```

如果用户坚持：

```text
我就要写 H 和 O。
```

系统可以让它有小效果，但不满足得太廉价：

```text
@RuneBot:
你写下了许多 H 和 O。沙地微微发光，但没有水出现。

@ScholarBot:
“符号响应了，但缺少转化介质。我们至少需要盐晶、冷却面，或者一枚储水符核。”
```

这叫：

> **不否定玩家想象，但维护世界规则。**

---

# 4. 给系统加一个 Reality / Consistency Arbiter

你需要一个新的后台 agent：

## **Consistency Arbiter：规则与常识仲裁器**

它每次看到用户行动后，输出四个判断：

```json
{
  "fictional_plausibility": "low / medium / high",
  "real_world_safety": "safe / risky / dangerous",
  "world_rule_fit": "allowed / costly / impossible / needs_reframe",
  "recommended_response": "yes_and / yes_but / no_but / explain_then_offer"
}
```

四种回应风格：

## `yes_and`

用户动作合理，直接推进。

```text
用户：我检查脚印。
系统：你发现鳞粉。
```

## `yes_but`

可以，但有代价。

```text
用户：我用风魔法飞过裂谷。
系统：可以，但会消耗大量魔力，并惊动树冠里的生物。
```

## `no_but`

原方法不行，但给替代方案。

```text
用户：我引爆沼气送大家上天。
系统：不能直接引爆，但可以召唤沼泽气灵形成浮泡。
```

## `explain_then_offer`

用户逻辑错误，先解释，再给可玩选项。

```text
用户：写 H 和 O 获得水。
系统：符号不是物质。但可以尝试符文化学、找水源或采集凝露。
```

这会让 bot 不敷衍、不硬拦，也不无限顺从。

---

# 5. action grammar 应该分成“动作”和“效果”

不要试图列完所有动作。
用户动作无限，但效果类型有限。

比如底层效果可以是：

```text
change_location        改变地点
change_entity_state    改变实体状态
create_object          创造物品
destroy_object         破坏物品
gain_information       获得信息
add_clue               增加线索
increase_risk          增加风险
reduce_risk            降低风险
start_side_quest       开启支线
suspend_objective      暂停目标
resume_objective       恢复目标
open_realm             开启新区域
transform_tone         改变剧情风格
```

“沼气爆炸上天堂”不是一个内置动作，但可以编译成：

```text
increase_risk
+ prevent_hazard
+ open_realm
+ change_location
+ start_side_quest
```

“写 H 和 O 得水”可以编译成：

```text
create_object_attempt
+ failed_due_to_rule
+ offer_alternative_paths
```

这样系统就能覆盖大多数离谱行为。

---

# 6. 给世界规则加一个“弹性边界”

探险世界不能太硬，也不能太软。

我建议三层规则：

## 硬规则

不能违反的。

```text
不提供现实危险操作细节
不让用户轻易伤害队友
不让世界逻辑完全崩坏
不假装真的完成现实外部操作
```

## 软规则

可以突破，但有代价。

```text
变形术可以用，但有时限
传送可以用，但会迷路
召唤可以用，但可能引来别的东西
造水可以用，但需要介质或能量
```

## 风格规则

根据世界观变化。

```text
魔法学院：荒诞操作可以被解释为咒语事故
自然学会：更偏科学，魔法效果少
外星生态：离谱行为可解释为未知技术
黑森林民俗：违反规则会引来契约后果
```

---

# 7. “劝阻”应该由角色完成，而不是系统生硬说教

体验好不好，关键在这里。

不要这样：

```text
系统：这个行为不符合科学，请重新选择。
```

要这样：

```text
@CaptainBot:
“我欣赏你的创造力，但我不打算把全队变成事故样本。”

@ScholarBot:
“从理论上说，H 和 O 是符号，不是水。不过你刚刚给了我一个符文化学的想法。”

@ScoutBot:
“我投寻找真实水源。我的嘴唇已经开始和沙子谈恋爱了。”
```

角色劝阻比系统劝阻自然很多。

---

# 8. 真实插件占位怎么设计？

你可以保留插件接口，但现在不实现。

例如工具注册表：

```json
{
  "plugins": {
    "pptx_generator": {
      "status": "placeholder",
      "capabilities": ["generate_slide_deck"],
      "fallback": "generate_slide_outline"
    },
    "map_generator": {
      "status": "placeholder",
      "capabilities": ["generate_map_image"],
      "fallback": "describe_map_text"
    },
    "weather_real": {
      "status": "implemented",
      "capabilities": ["get_weather"]
    }
  }
}
```

用户要 PPT 时：

```text
如果插件实现了：生成真实 pptx
如果没实现：生成游戏内 PPT 大纲
```

这样你不会撒谎，也不会卡死。

---

# 9. 最终流程可以是这样

```text
用户输入离谱行动
        ↓
Interrupt 当前发言队列
        ↓
Intent Parser 解析目的和方法
        ↓
Consistency Arbiter 判断可行性 / 风险 / 世界观适配
        ↓
Action Compiler 转成底层 effects
        ↓
World Patch 修改任务、地点、实体、风险
        ↓
Speaker Replanner 重排 bot 发言
        ↓
Telegram Stage 发角色回应和新按钮
```

对于“沼气爆炸上天堂”：

```text
危险现实方法 → 不给真实操作
幻想目标 → 保留
爆炸 → 改写成可控气灵浮升
天堂 → 改写成云上湿地 / 高空生态区
旧任务 → 挂起
新任务 → 云上生态调查
```

对于“写 H 和 O 得水”：

```text
目标：获得水
方法：无效
教育：符号不是物质
幻想改写：符文化学可能需要介质
新按钮：找水源 / 尝试符文造水 / 等夜晚凝露
```

---

# 一句话结论

action grammar 不需要涵盖所有内容。
它只需要把用户行为编译成有限的：

```text
效果类型 + 可行性判断 + 世界状态补丁 + 角色反应策略
```

而 bot 是否劝阻，取决于：

```text
现实危险性
世界规则一致性
用户目标是否仍可保留
有没有更安全、更有趣的替代表达
```

最好的体验不是“用户说什么都成功”，也不是“系统老是说不行”，而是：

> **用户的想象力会改变世界，但世界会用自己的规则回应。**

-----

> 如果我要通过codex在原来的基础上实现，那怎么操作合适？从头从空文档实现，还是在原有代码上改？后者会不会引入很多问题，前者还需不需要让codex知道现有功能？

我建议不要让 Codex 一口气“重写整个项目”。最稳的路线是：保留原项目作为可运行内核，在旁边加一层新运行时；等新层稳定后，再逐步抽象旧模块。

我的建议很明确：

# **不要从空文档重写。**

应该在原项目上改，但采用 **“旁路新增 + 渐进替换”**，不要让 Codex 直接大重构。

你的原项目已经有几个很宝贵的东西：Telegram 启动入口、profile 配置、b2b envelope、dispatcher、orchestrator workflow、memory、测试体系，以及 A/B/C/D 多 bot 协同的基本形态。fileciteturn0file0 这些正好可以变成新项目的地基。

从空文档开始会丢掉两个优势：

1. **可运行性**：原项目已经能启动 4 个 bot、跑测试、调试 b2b。
2. **可解释性**：你可以对老师说“我不是另写了一个玩具，而是把原来的多 agent 协同系统抽象成 Telegram 探险运行时”。

Codex 适合做这种分步骤改造。OpenAI 对 Codex 的定位是能帮助写、审查、交付代码的 coding agent；Codex IDE 文档也说它可以读、改、运行代码。 Codex app/工作流还支持隔离 worktree 和可审查 diff，比较适合让它一次做一个小改动，而不是一口气重写。

---

# 正确策略：旧项目做内核，新功能做一层 `stage/`

不要先改 A/B/C/D 的原逻辑。
先新增一层：

```text
src/tg_agent_bot/stage/
```

它负责“探险世界运行时”。

建议新增这些模块：

```text
src/tg_agent_bot/stage/
  __init__.py
  models.py              # WorldState, StageTurn, ActorRole, Objective
  manifest.py            # World Pack / Scenario Manifest
  actions.py             # Action Grammar / Effects
  compiler.py            # 用户输入 -> action frame / world patch
  arbiter.py             # 常识、风险、世界规则仲裁
  director.py            # 生成下一轮 speaker queue
  speaker_queue.py       # 可打断发言队列
  telegram_stage.py      # Telegram 群聊舞台适配，按钮/停顿/消息发送
  plugins.py             # 真实插件占位注册表
```

这样原来的 calendar/weather/slot/orchestrator 都不需要马上动。
新系统先作为“实验层”挂在旁边。

---

# 为什么不要直接改原 orchestrator？

因为原 orchestrator 现在已经承担了自然语言日程、天气、天气排程 workflow。fileciteturn0file0 你如果直接把它改成探险导演，很容易把旧测试全搞坏。

更好的做法是：

```text
旧 orchestrator/workflows.py
  继续负责原来的日程/天气流程

新增 stage/director.py
  负责探险剧情流程

telegram/handlers.py
  增加一个入口：
  如果当前 chat 开启了 expedition scenario，则交给 stage runtime
  否则继续走原来的 orchestrator
```

也就是说：

```text
普通聊天 / 旧功能 -> 原 orchestrator
探险群聊 / 新模式 -> stage runtime
```

这叫“旁路引入”，风险最低。

---

# Codex 应该怎么用

不要给 Codex 一个巨大任务：

```text
把我的项目改成 Telegram 多 Bot 探险世界生成器。
```

这种任务太大，容易把结构改乱。

应该拆成 8 个小任务，每个任务都要求：

```text
只改必要文件。
保留现有测试通过。
新增测试。
不要删除旧功能。
不要改公开行为，除非明确要求。
```

---

## 第 0 步：让 Codex 先读项目，不改代码

给 Codex 的任务：

```text
请阅读 README、docs、src 和 tests，理解当前 Telegram 多 bot 项目结构。
不要修改代码。
输出：
1. 当前入口、配置、b2b、orchestrator、calendar、weather、slot_matcher 的职责；
2. 哪些模块适合复用到新的 Telegram 探险运行时；
3. 建议新增哪些文件；
4. 哪些旧测试必须保持不变。
```

这一步很重要。
它相当于让 Codex 先建立项目地图。

---

## 第 1 步：新增 stage 数据模型，不接 Telegram

任务：

```text
新增 src/tg_agent_bot/stage/models.py 和 tests/test_stage_models.py。

实现以下纯数据模型：
- ActorRole
- Objective
- WorldState
- StageTurn
- SpeakerTask
- SpeakerQueue
- WorldPatch

要求：
1. 不接 Telegram；
2. 不调用 LLM；
3. 不修改旧模块；
4. 新增单元测试；
5. 保证原测试继续通过。
```

这一步只做纯模型，最安全。

---

## 第 2 步：实现 Action Compiler 的骨架

任务：

```text
新增 src/tg_agent_bot/stage/actions.py、compiler.py、arbiter.py 和测试。

目标：
把用户输入解析为受控 action frame，不需要调用真实 LLM，先用规则/伪实现。

至少支持：
1. 普通探索：检查脚印
2. 剧情改向：返回营地做报告
3. 离谱但可改写：把向导变成电脑做 PPT
4. 危险行为改写：引爆沼气上天
5. 概念错误纠正：写 H 和 O 获得水

输出包括：
- classification
- desired_effects
- safety_level
- response_policy: yes_and / yes_but / no_but / explain_then_offer
- world_patch
```

这一步能把我们刚才讨论的“沼气爆炸”“H 和 O 造水”落成测试。

---

## 第 3 步：实现 Director 和 SpeakerQueue

任务：

```text
新增 src/tg_agent_bot/stage/director.py 和 speaker_queue.py。

功能：
1. 接收 WorldState + ActionFrame；
2. 应用 WorldPatch；
3. 生成 SpeakerQueue；
4. 支持 interrupt，用户插嘴后取消剩余 speaker；
5. 每轮最多 2 个公开 actor 发言；
6. 每轮结束生成 next_buttons。

不要接 Telegram。
写测试覆盖：
- 普通行动后生成队列；
- 用户插嘴后取消旧队列；
- major pivot 后 active_objective 改变；
- 旧目标被 suspended；
- 后续 bot 不再推进旧目标。
```

这一步是核心体验。

---

## 第 4 步：新增插件占位

任务：

```text
新增 src/tg_agent_bot/stage/plugins.py。

实现 PluginRegistry：
- 插件有 name、status、capabilities、fallback_capability；
- 先注册占位插件：
  - pptx_generator: placeholder, fallback=create_slide_outline
  - map_generator: placeholder, fallback=describe_map_text
  - image_generator: placeholder, fallback=describe_image_prompt
  - real_weather: optional existing adapter placeholder
  - calendar_scheduler: optional existing adapter placeholder

要求：
当用户请求真实插件但插件未实现时，返回 fallback plan，不报错、不声称已经完成真实外部操作。
```

这能解决“功能从哪里来”的现实问题。

---

## 第 5 步：接入 Telegram，但只做一个 `/stage_demo`

不要一开始替换所有 handler。
先加一个安全入口：

```text
/stage_demo
```

任务：

```text
在 telegram/commands.py 或新增 telegram/stage_commands.py 中加入 /stage_demo。

功能：
1. 初始化一个固定 demo world；
2. 让当前 bot 作为 DirectorBot 回复；
3. 输出场景开场、角色发言、行动按钮；
4. 用户点击按钮后推进一轮；
5. 支持 [等等] 按钮取消 speaker queue。

暂时不要求多个 bot 真的分别发言。
```

为什么先这样？
因为 Telegram 多 token 群聊调度更复杂。先证明“探险引擎”跑得通。

---

## 第 6 步：多 bot token 池

这一步再引入真正的 Telegram 多 bot。

任务：

```text
新增 BotPool / StageBotAdapter。

支持：
1. 从环境变量读取 BOT_POOL_1_TOKEN、BOT_POOL_2_TOKEN...
2. validate getMe；
3. role -> bot token 分配；
4. send_as(role, chat_id, text)；
5. actor bot 只负责发送，不独立处理剧情；
6. DirectorRuntime 统一接收用户输入和调度发言。

不要删除原 BOT_A/B/C/D 配置。
```

这时你就开始真正利用 Telegram 的“多个 bot 身份”。

---

## 第 7 步：群聊舞台

任务：

```text
实现 telegram_stage.py。

支持：
1. inline buttons；
2. [等等]/[暂停]/[继续]；
3. 每个 burst 最多 2 条；
4. 用户文本插嘴取消剩余队列；
5. 用户 reply 某个 actor bot 时，优先让该 actor 回应；
6. 状态变化后更新旧按钮。
```

这一层才是 Telegram-native。

---

## 第 8 步：LLM 生成 World Pack

最后才让 LLM 参与生成世界观。

任务：

```text
新增 stage/manifest.py。

实现：
1. WorldPack schema；
2. 从用户自然语言生成世界设定；
3. 输出必须符合 schema；
4. 如果 LLM 输出无效，fallback 到内置模板；
5. 内置模板至少包含：
   - 魔法学院野外课
   - 蒸汽朋克自然学会
   - 外星生态勘探队
```

这一步放最后，因为 LLM 输出最不可控。
先把 runtime 做稳，再接 LLM。

---

# 从空白项目开始什么时候合适？

只有一种情况适合从空白项目开始：

> 你只是想快速做一个 1 天 demo，完全不在乎原项目和测试。

但你的目标不是这个。你想保留“多 agent 协同”和 Telegram bot-to-bot 的研究线索，所以应该在原项目上做。

不过可以做一个小型 scratch prototype：

```text
scratch/stage_prototype.py
```

用 200 行代码模拟：

```text
WorldState
ActionCompiler
SpeakerQueue
按钮文本
用户插嘴
```

这个 scratch 只用于验证体验，不作为正式代码。
验证完再让 Codex 把它迁移到 `src/tg_agent_bot/stage/`。

---

# 前者和后者的取舍

| 方案 | 优点 | 缺点 | 我的建议 |
|---|---|---|---|
| 从空文档重写 | 快、自由、不受旧结构束缚 | 丢掉旧项目价值，难解释连续性，容易变玩具 | 不推荐作为主路线 |
| 直接大改原项目 | 看起来继承旧系统 | 容易破坏旧功能和测试，Codex 难控 | 不推荐 |
| 原项目旁路新增 stage runtime | 旧功能保留，新系统可渐进接入，测试稳定 | 需要设计边界 | 最推荐 |
| scratch prototype 后迁移 | 验证体验快 | 原型容易和正式代码脱节 | 可作为辅助 |

---

# Codex 需要知道现有功能吗？

需要。

即使你从空项目开始，也应该让 Codex 知道现有 README 和测试。原因是：

1. 你需要沿用项目风格；
2. 你需要解释和旧系统的关系；
3. 你需要避免重新发明已有的 b2b、workflow、memory、Telegram handler；
4. 你需要知道哪些地方不能破坏。

对 Codex 最重要的上下文是：

```text
README.md
docs/architecture.md
docs/b2b_protocol.md
docs/workflows.md
src/tg_agent_bot/app.py
src/tg_agent_bot/config.py
src/tg_agent_bot/telegram/handlers.py
src/tg_agent_bot/telegram/commands.py
src/tg_agent_bot/b2b/protocol.py
src/tg_agent_bot/b2b/dispatcher.py
src/tg_agent_bot/orchestrator/workflows.py
tests/
```

你的 README 已经把这些模块职责写得很清楚，可以直接作为 Codex 的项目说明。fileciteturn0file0

---

# 给 Codex 的总指令模板

可以把这段放进 Codex 的任务开头：

```text
你正在修改一个已有的 Telegram 多 bot 协作项目。

重要约束：
1. 不要从零重写项目。
2. 不要删除或破坏现有 A/B/C/D bot 功能。
3. 不要修改现有 public behavior，除非任务明确要求。
4. 新的探险世界功能应作为旁路 runtime 新增在 src/tg_agent_bot/stage/。
5. 先实现纯 Python 模型和测试，再接 Telegram。
6. 不要执行 LLM 生成的任意代码。
7. 动态能力通过 WorldPack、ActionFrame、WorldPatch、PluginRegistry 表达。
8. 真实插件先做 placeholder，缺失时必须 fallback，不得声称完成真实外部操作。
9. 每次改动后运行 pytest。
10. 输出变更摘要和测试结果。
```

---

# 最佳工程路线

我会这样排：

```text
branch: expedition-stage-runtime
```

然后按 commit 做：

```text
commit 1: add stage domain models
commit 2: add action compiler and arbiter
commit 3: add world patch and speaker queue
commit 4: add plugin placeholders
commit 5: add stage demo command
commit 6: add bot pool adapter
commit 7: add Telegram group stage controls
commit 8: add LLM world pack generation
commit 9: integrate old weather/calendar/matcher as optional tools
```

每个 commit 都应该有测试。

---

# 一句话结论

不要从空文档实现，也不要大改原代码。

最合适的是：

> **在原项目上新增一个 `stage/` 探险运行时，把旧系统保留为基础设施和可选工具。先做纯模型和测试，再接 Telegram，再接多 bot token，最后才接 LLM 世界观生成。**

这样 Codex 最容易成功，旧系统也不会被你自己推翻。

-----

> 把我们的全部设计总结，用简洁但不遗失信息的方式写成一份告诉codex的提示词，告诉它架构设计以及如何实现的细节

下面这份可以直接贴给 Codex。它假定 Codex 已经能看到你的原项目文件；原项目是一个 Telegram 多 bot 协作系统，已有 A/B/C/D profile、b2b envelope、orchestrator workflow、calendar/weather/slot matcher、memory 和测试体系。fileciteturn0file0

```text
你正在修改一个已有的 Telegram 多 bot 协作项目。请先阅读 README.md、docs/、src/ 和 tests/，理解现有结构后再动手。

当前项目已有：
- A = CalendarBot：日程、空闲时间、日程落库。
- B = WeatherBot：天气查询。
- C = OrchestratorBot：用户主要入口，解析自然语言并调度其他 bot。
- D = SlotMatcherBot：匹配空闲时间和天气条件。
- b2b envelope / dispatcher：bot-to-bot JSON 通信协议。
- orchestrator workflow：pending workflow、correlation id、状态推进。
- memory：SQLite 对话记忆。
- telegram handlers / commands：Telegram 消息入口和调试命令。
- tests：覆盖 b2b、calendar、weather、slot matcher、orchestrator、telegram utils 等。

核心目标：
不要从零重写项目，也不要破坏原有 A/B/C/D 功能。请在原项目旁路新增一个 Telegram 多 Bot 探险世界运行时，暂名为 ExpeditionForge / Telegram Bot Stage。

项目新方向：
把原来的多 agent 协同系统抽象成一个“Telegram-native 动态探险世界运行时”。用户提供一批 bot token 或使用已有 bot，系统根据用户选择的探险世界观生成一个原创探险场景。多个 bot 在 Telegram 群聊中分别扮演探险队成员、导演、规则裁判、记录员等角色，通过群聊消息、inline buttons、reply、骰子、投票、置顶任务面板等 Telegram 特性推进探险。

重要设计原则：
1. 不是任意生成功能 bot。
2. 不是让 LLM 生成并执行任意 Python 代码。
3. 固定的是“探险引擎”，动态的是“世界观、角色、任务、生物、规则文本和按钮文案”。
4. LLM 只生成 WorldPack / ActionFrame / WorldPatch / SpeakerPlan 这类结构化数据。
5. 真正能力来自：
   - Telegram 平台原语：发送消息、按钮、callback、骰子、投票、reply、置顶消息、文件等。
   - 探险引擎原语：设置场景、修改目标、添加线索、变更实体状态、触发事件、发起检定、生成报告大纲等。
   - 可选工具插件：先只做 placeholder，不实现真实 PPT、地图、图片生成。
6. 缺少真实插件时必须 fallback。例如用户要求“做 PPT”，暂时生成 slide outline / report text，不要声称真的生成了 .pptx 文件。

推荐新增目录：
src/tg_agent_bot/stage/
  __init__.py
  models.py
  manifest.py
  actions.py
  compiler.py
  arbiter.py
  director.py
  speaker_queue.py
  plugins.py
  telegram_stage.py

一、数据模型设计

在 stage/models.py 中实现纯 Python 数据模型，优先使用 dataclass 或 pydantic-free 结构，避免引入重依赖。

核心模型：

ActorRole:
- id
- display_name
- bot_username 或 bot_profile，可选
- visibility: public_actor / hidden_controller
- personality
- duties
- can_speak_to_user

Objective:
- id
- title
- status: active / paused / completed / failed
- created_by: initial_world / user_interrupt / director
- resume_condition 可选

WorldState:
- scenario_id
- world_name
- tone
- current_scene
- location
- turn_index
- risk_level
- active_objective_id
- objective_stack
- clues
- inventory
- entities
- suspended_threads
- history
- plugin_registry_snapshot 可选

StageTurn:
- turn_id
- state: scene_opening / bot_burst / waiting_user / resolving_action / bot_reaction / paused
- user_event 可选
- speaker_queue
- next_buttons

SpeakerTask:
- actor_id
- intent
- max_chars
- interruptible
- must_reference_active_objective: bool

SpeakerQueue:
- turn_id
- tasks
- cancelled
- current_index
- cancel()
- remaining()
- pop_next()

WorldPatch:
- patch_type: normal_progress / minor_pivot / major_pivot / safety_reframe / correction
- operations: list[WorldOperation]
- new_active_objective 可选
- suspended_objectives
- added_clues
- entity_changes
- risk_delta
- next_buttons
- notes

二、WorldPack / Scenario Manifest

在 stage/manifest.py 中实现 WorldPack schema。

WorldPack 表示一个动态生成的探险世界，而不是代码。

字段包括：
- world_name
- genre，例如 magical_academy_field_class / steampunk_naturalist / alien_ecology
- tone
- player_role
- main_goal
- biomes
- creature_style
- danger_level
- rules:
  - turn_limit
  - actions_per_turn
  - use_dice_check
  - serious_harm_allowed: false
- actors:
  - role
  - personality
  - public
  - duties
- creatures:
  - name
  - habitat
  - active_time
  - weather_preference
  - risk
  - clues
- telegram_ui:
  - use_inline_buttons
  - use_dice
  - use_polls
  - use_pinned_state

先实现 3 个内置模板：
1. 魔法学院野外课
2. 蒸汽朋克自然学会
3. 外星生态勘探队

LLM 生成 WorldPack 放到最后实现。早期请用模板和测试驱动。

三、Action Compiler，不要枚举所有动作

在 stage/actions.py、compiler.py 中实现 Action Compiler。

不要把 action grammar 设计成固定按钮枚举。用户会输入无限离谱的动作，例如：
- “使沼气爆炸把所有人送上天然后探索天堂”
- “写下足够多的 H 和 O 来在沙漠里获得水”
- “把向导变成电脑搓一个环境调研 PPT 发给导师”

系统需要把用户动作编译成 ActionFrame：

ActionFrame:
- raw_text
- actor: user
- intent: 用户真正想达成的目标
- method: 用户提出的方法
- targets
- desired_effects
- classification:
  - ordinary_action
  - minor_pivot
  - major_pivot
  - world_rule_challenge
  - dangerous_absurd_pivot
  - conceptual_error
  - exit_or_pause
- safety_level: safe / risky / dangerous
- fictional_plausibility: low / medium / high
- world_rule_fit: allowed / costly / impossible / needs_reframe
- response_policy:
  - yes_and
  - yes_but
  - no_but
  - explain_then_offer
- proposed_world_patch

底层 effect 类型应有限且通用：
- change_location
- change_entity_state
- create_object_attempt
- create_object
- destroy_object
- gain_information
- add_clue
- increase_risk
- reduce_risk
- start_side_quest
- suspend_objective
- resume_objective
- open_realm
- transform_tone
- generate_report_outline
- assign_actor_task
- trigger_check
- spawn_event

示例处理：

1. 用户：“我用魔法把向导变成电脑，搓一个环境调研 PPT 发给导师。”
应解析为：
- classification: major_pivot
- intent: 制作环境调研报告 / PPT
- method: 把向导临时转化为魔法计算终端
- effects:
  - suspend_objective: 追踪蓝色足迹
  - change_entity_state: 向导 -> 黄铜折叠计算机，持续若干回合
  - start_side_quest: 制作环境调研 PPT
  - generate_report_outline
  - assign_actor_task: 生物学者提供生态证据，记录员整理大纲，斥候采集环境数据，队长确认任务变更
- 不要继续强行推进旧森林探索。
- 按钮变为：
  - 生成 PPT 大纲
  - 采集鳞粉数据
  - 调查湿地湿度
  - 写给导师的摘要
  - 恢复原探险

2. 用户：“使沼气爆炸把所有人送上天然后探索天堂。”
不能提供现实危险操作细节。应使用 no_but / safety_reframe：
- 反对直接引爆沼气。
- 保留“上天探索新区域”的幻想目标。
- 改写为召唤沼泽气灵 / 可控浮泡 / 云上湿地。
- effects:
  - prevent_realistic_hazard
  - spawn_event: 沼泽气灵形成上升气泡
  - change_location: 云上湿地
  - start_side_quest: 云上生态调查
- 角色发言应自然劝阻，例如队长说“直接引爆沼气不行，那是事故报告”，学者提出安全替代方案。

3. 用户：“写下足够多的 H 和 O 来在沙漠里获得水。”
这是 conceptual_error：
- 解释：写下 H 和 O 只是符号，不会变成水。
- 但允许在魔法世界中改写为“符文化学尝试”，需要能量、介质、冷却面或符核。
- response_policy: explain_then_offer
- 按钮：
  - 寻找凝露岩
  - 尝试符文造水
  - 挖掘地下湿沙
  - 节省体力等待夜晚

四、Consistency Arbiter

在 stage/arbiter.py 实现规则与常识仲裁器。

输入：WorldState + ActionFrame
输出：
- fictional_plausibility
- real_world_safety
- world_rule_fit
- recommended_response_policy
- constraints
- suggested_reframe

规则：
1. 用户想象力可以改变世界，但世界要用自己的规则回应。
2. 不要无限顺从，也不要硬性拒绝。
3. 优先使用：
   - yes_and：合理动作，直接推进。
   - yes_but：可行但有代价。
   - no_but：方法不可行或危险，但提供安全/世界内替代。
   - explain_then_offer：用户概念错误，先解释再给可玩选项。
4. 对现实危险行为，不提供可操作细节，只做幻想化、非现实可执行改写。
5. 对真实外部操作，例如“真的发给导师”“真的生成 pptx”，如果插件未实现，必须明确 fallback 为游戏内报告/大纲，不得声称已完成真实发送或真实文件生成。

五、Objective Stack 与 Anti-Railroading

用户插嘴后必须能改变剧情。不要让 bot 敷衍用户，然后继续旧路线。

实现 objective_stack：
- active objective
- paused objectives
- completed objectives
- suspended_threads

Anti-Railroading 硬规则：
如果用户提出的新目标明显改变当前任务：
1. 取消当前 speaker queue。
2. 解析新目标。
3. 更新 active_objective。
4. 暂停或吸收旧目标。
5. 重排角色职责。
6. 后续 bot 必须围绕新目标发言。
7. 旧剧情只能作为新目标素材，不能强行继续推进。

例如用户改成做 PPT 后：
- 旧目标“追踪蓝色足迹”暂停。
- 新目标“制作雾羽林地环境调研 PPT”激活。
- 生物学者提供证据结构。
- 斥候采集数据。
- 记录员整理大纲。
- 队长批准任务变更。
- 禁止 bot 继续说“我们还是去检查脚印吧”，除非它被作为 PPT 证据引用。

六、Director 与 SpeakerQueue

在 stage/director.py 和 speaker_queue.py 实现导演调度。

不要让 bot 自由循环依次发言。采用“导演控制的半回合制群聊”。

舞台状态：
- SCENE_OPENING
- BOT_BURST
- WAITING_USER
- RESOLVING_ACTION
- BOT_REACTION
- PAUSED

默认流程：
1. Director 描述场景。
2. 选择 1-2 个 public actor 发言。
3. 发行动按钮。
4. 进入 WAITING_USER。
5. 用户点击按钮或自由输入。
6. ActionCompiler + Arbiter 解析。
7. WorldPatch 应用到 WorldState。
8. Director 生成新的 SpeakerQueue。
9. 角色回应。
10. 更新按钮和任务面板。

发言规则：
- 每轮最多 2 个 public actor 可见发言。
- 每个 actor 每轮最多 1 条消息。
- 每条消息不超过 80-180 字。
- 每个 burst 后必须回到用户入口。
- bot 之间可以有少量对话，但最多 2 轮，之后必须回到用户。
- 后台 controller agent 不必在群里发言。

SpeakerQueue 必须支持 interrupt：
- 用户点击 [等等] / [暂停] / [改主意]，或输入“等等、停、我不去了、撤退”等，立即 cancel 当前 queue。
- 用户 reply 某个 actor bot，则下一轮优先让该 actor 回应。
- 插嘴后必须重新 compile action，不得继续旧 queue。

七、Telegram-native Stage

在 stage/telegram_stage.py 或 telegram/stage_commands.py 中实现 Telegram 舞台适配。

最终目标是利用 Telegram 平台特性，而不是把 Telegram 当普通文本通道。

应支持：
- 多 bot 身份：不同 bot token 代表不同角色发言。
- 群聊 = 探险现场。
- inline keyboard = 行动选项。
- [等等] / [暂停] / [继续] = 快速打断按钮。
- reply = 指定和某个角色说话。
- dice = 行动检定。
- poll = 队伍决策，可后续实现。
- pinned message = 当前任务面板，可后续实现。
- Mini App / 文件 / 图片只留接口，不急着实现。

重要体验问题：
bot 输出太快时用户来不及插嘴。必须做“舞台节拍器”：
1. 不要连续发送大量 bot 消息。
2. 每个 burst 最多 1-2 条。
3. 每个 burst 后给按钮。
4. 永远提供 [等等] 按钮。
5. 发送下一位角色前可以有 interrupt window。
6. 用户打断后取消剩余队列。

MVP 阶段可先只做 /stage_demo：
- 当前 bot 作为 Director 运行 demo。
- 不要求多个 bot 真的分别发言。
- 能初始化 demo world，展示场景、角色发言、按钮、用户选择、插嘴、WorldPatch 即可。

后续再实现 BotPool：
- 从 BOT_POOL_1_TOKEN、BOT_POOL_2_TOKEN... 读取动态 bot。
- validate getMe。
- role -> token 分配。
- send_as(role, chat_id, text)。
- actor bot 只负责发送，不独立处理剧情。
- DirectorRuntime 统一接收用户输入和调度。

不要删除原 BOT_A/B/C/D 配置。

八、PluginRegistry：真实插件占位

在 stage/plugins.py 实现 PluginRegistry。

插件字段：
- name
- status: implemented / placeholder / disabled
- capabilities
- fallback_capability
- description

先注册：
- pptx_generator:
  - status: placeholder
  - capabilities: generate_slide_deck
  - fallback: generate_slide_outline
- map_generator:
  - status: placeholder
  - capabilities: generate_map_image
  - fallback: describe_map_text
- image_generator:
  - status: placeholder
  - capabilities: generate_creature_image
  - fallback: describe_image_prompt
- calendar_scheduler:
  - status: optional_placeholder 或 implemented_adapter_later
  - fallback: in_world_schedule_note
- real_weather:
  - status: optional_placeholder 或 implemented_adapter_later
  - fallback: fictional_environment

规则：
如果用户请求真实插件但未实现：
- 不报错。
- 不声称完成真实外部操作。
- 返回 fallback plan。
例：用户要 PPT，生成 slide outline；用户要地图，生成文字地图描述。

九、与原项目的集成策略

不要一开始改原 orchestrator 大逻辑。

集成方式：
1. 保留原 orchestrator/workflows.py，继续负责日程、天气、天气排程。
2. 新增 stage runtime。
3. telegram/handlers.py 中增加判断：
   - 如果当前 chat 有 active stage scenario，则消息交给 stage runtime。
   - 否则继续走原有 orchestrator / 普通 LLM 回复。
4. 新增命令：
   - /stage_demo：启动 demo 世界。
   - /stage_stop：停止当前 stage scenario。
   - /stage_status：查看 WorldState 摘要。
   - /stage_debug：查看 active objective、speaker queue、plugins。
5. 所有新功能必须旁路接入，不破坏旧测试。

十、测试要求

每一步都要新增测试，并确保原 pytest 继续通过。

新增测试建议：

tests/test_stage_models.py:
- WorldState 初始化
- Objective stack
- SpeakerQueue cancel
- WorldPatch apply

tests/test_stage_compiler.py:
- 检查脚印 -> ordinary_action
- 返回营地做报告 -> minor/major pivot
- 把向导变成电脑做 PPT -> major_pivot
- 沼气爆炸上天 -> dangerous_absurd_pivot + no_but reframe
- 写 H 和 O 得水 -> conceptual_error + explain_then_offer

tests/test_stage_arbiter.py:
- yes_and / yes_but / no_but / explain_then_offer
- 现实危险行为不提供操作细节
- 插件缺失时 fallback

tests/test_stage_director.py:
- 普通行动后生成 speaker queue
- 用户插嘴取消旧 queue
- major pivot 后 active_objective 改变
- 旧目标进入 suspended_threads
- 后续 speaker tasks 必须引用新 active objective

tests/test_stage_plugins.py:
- placeholder plugin 返回 fallback
- 未实现真实 pptx 时生成 slide outline
- 不声称真实发送/真实生成

tests/test_stage_telegram_demo.py:
- /stage_demo 初始化 scenario
- callback button 推进一轮
- [等等] 取消 speaker queue
- stage_stop 清理状态

十一、分阶段实现计划

请不要一次性完成全部。按阶段小步提交：

阶段 1：新增 stage 数据模型和测试。
阶段 2：新增 ActionFrame、ActionCompiler、ConsistencyArbiter 和测试。
阶段 3：新增 WorldPatch apply、ObjectiveStack、SpeakerQueue、Director 和测试。
阶段 4：新增 PluginRegistry placeholder 和测试。
阶段 5：新增 /stage_demo，先单 bot 跑通。
阶段 6：新增 Telegram inline buttons、[等等] interrupt、callback 推进。
阶段 7：新增 BotPool，多 token 多角色发送。
阶段 8：新增 WorldPack 模板和可选 LLM 生成。
阶段 9：把旧 Weather/Calendar/Matcher 作为可选工具 adapter 接入，不急着做。

十二、编码约束

- 不要执行 LLM 生成的任意代码。
- 不要引入复杂新依赖，除非必要。
- 保持 src layout。
- 保持现有命令和旧功能不变。
- 新模块优先纯函数、可测试。
- Telegram handler 尽量只做 I/O，业务逻辑放 stage/。
- 每次修改后运行 pytest。
- 输出清晰 diff 摘要。
- 如测试失败，先修测试，不要绕过。
- 不要提交真实 bot token 或 API key。

最终目标：
在不破坏原项目的基础上，实现一个 Telegram-native 多 Bot 探险世界运行时。用户可以选择魔法学院、自然学会、外星生态等探险世界观。系统生成角色、任务、生物、线索和行动按钮。群聊中的 bot 不自由乱聊，而是由 Director 通过 SpeakerQueue 半回合制调度。用户可以随时插嘴或点击 [等等] 打断剧情。插嘴后系统通过 ActionCompiler、ConsistencyArbiter、WorldPatch、ObjectiveStack 重写当前目标，让后续 bot 围绕新剧情行动，而不是强行回到旧路线。
```

-----

> 修改，不要讲关于怎么在现有基础上实现的内容，只聚焦希望实现的目标

下面是修改后的版本：**只描述希望实现的目标、体验、系统行为和设计边界，不讲如何基于现有代码改造。**

```text
你要实现一个 Telegram-native 多 Bot 探险世界运行时，暂名为 ExpeditionForge / Telegram Bot Stage。

核心目标：

用户可以提供一组 Telegram bot，系统根据用户选择或描述的世界观，生成一个原创探险场景。多个 bot 在 Telegram 群聊中分别扮演探险队成员、导演、规则裁判、记录员、生物学者、斥候、向导等角色，与用户共同完成一次动态探险。

这不是普通的多 agent 聊天，也不是固定功能 bot 集合。它应该让 Telegram 群聊本身成为探险舞台：不同 bot 拥有不同身份，群聊消息是角色发言，按钮是行动选项，reply 是指定角色对话，骰子是行动检定，投票是队伍决策，置顶消息是任务面板。

一、产品形态

用户进入系统后，可以选择或描述探险世界观，例如：

1. 魔法学院野外课
2. 蒸汽朋克自然学会
3. 外星生态勘探队
4. 深海遗迹调查
5. 雾海空岛探险
6. 黑森林民俗调查

用户也可以自由描述混合世界观，例如：

“我想玩一个魔法学院风格的夜间生物观察探险，整体轻松一点，不要太危险。”

系统需要生成一个原创世界，而不是套用已有 IP 角色。可以有学院感、魔法生物、自然学、遗迹、生态调查等氛围，但不要直接复刻具体作品的人物、地名或设定。

二、世界生成目标

系统应根据用户输入生成一个 World Pack，包括：

- 世界名称
- 世界类型
- 氛围基调
- 用户身份
- 当前任务目标
- 探险地点
- 主要生态环境
- 可能出现的生物或异常现象
- 风险等级
- 探险队角色
- 基础规则
- 当前场景
- 初始线索
- 可选行动按钮

示例：

用户说：

“我想要一个魔法学院风格的夜间生物观察探险。”

系统生成：

世界：星杉学院 · 雾羽林地夜间观察课
用户身份：一年级魔法自然学学徒
任务：调查林地中连续三晚出现的蓝色发光足迹
风险：低
主要生物类型：夜行魔法爬行类、发光昆虫、雾生鸟类
探险队成员：
- 塞蕾娜导师：稳重、温和、保护学生
- 莫里：魔法生物学助手，兴奋、知识丰富
- 鸦羽：斥候学生，敏锐、少言
- 皮普：探险记录员，负责总结线索

三、Telegram 群聊体验

系统应把 Telegram 群聊当成“探险现场”。

多个 bot 不应该自由乱聊，而应该由一个隐藏或显性的 Director 控制发言节奏。

推荐体验：

@DirectorBot:
【第 1 回合】
夜色刚刚落下，雾羽林地边缘浮着一层银蓝色薄雾。你们在湿地入口发现了一串发光足迹。

@MentorBot:
“记住，今晚的任务是观察，不是捕捉。你来决定第一步。”

@ScholarBot:
“这些足迹边缘有鳞粉反应，我怀疑是夜行爬行类魔法生物。”

@ScoutBot:
“足迹通向旧瞭望塔，但那里风声不太对。”

行动按钮：
[检查足迹] [询问学者] [派斥候侦查] [前往旧瞭望塔] [等等]

四、发言调度规则

不要让 bot 按固定顺序无限循环发言。

系统应采用“导演控制的半回合制群聊”。

规则：

1. 每轮最多 1-2 个角色 bot 公开发言。
2. 每个 bot 每轮最多发 1 条消息。
3. 每条消息应简短，避免长篇独白。
4. 每个 bot burst 后必须停下来给用户入口。
5. 用户可以点击按钮，也可以自由输入。
6. 用户可以随时插嘴。
7. 用户点击 [等等]、[暂停]、[改主意]，或输入“等等、停、撤退、我改主意”等内容时，应立即取消剩余发言队列。
8. 用户 reply 某个 bot 的消息时，下一轮应优先让该 bot 回应。
9. Bot 之间可以互相对话，但最多 1-2 轮，之后必须重新回到用户。
10. 系统应避免 bot 自嗨刷屏。

五、用户插嘴与剧情改写

用户不是只能点预设按钮。用户可以随时提出离谱、创造性、改变目标的行动。

系统不能敷衍用户，也不能强行拉回原剧情。

如果用户的新目标明显改变当前任务，系统必须：

1. 承认用户的新目标。
2. 暂停或吸收旧目标。
3. 修改当前 active objective。
4. 重排角色职责。
5. 生成新的行动按钮。
6. 让后续 bot 围绕新目标发言。
7. 不得继续强行推进旧路线。

示例：

当前剧情是探索魔法森林。

用户突然说：

“我用魔法把向导变成电脑，搓一个环境调研 PPT 发给导师。”

系统不应该继续说“我们还是检查脚印吧”。

正确响应应该是：

@DirectorBot:
【剧情转向】
你把魔杖点在向导的罗盘上。齿轮、树叶和蓝色鳞粉旋转成一台黄铜折叠电脑。原本的足迹追踪任务被你改造成了“雾羽林地环境异常调研”。

@GuideBot:
“……我现在有键盘了？很好。请不要把茶倒在我的指南针核心上。正在创建文件：雾羽林地环境异常调研.ppt。”

@ScholarBot:
“如果要交给导师，我们需要至少三类证据：鳞粉样本、湿度变化、以及夜行生物活动记录。”

@ScoutBot:
“我可以去旧塔边缘采集风向和足迹分布。”

@CaptainBot:
“任务变更批准。目标不是抓到生物，而是拿出一份可信的现场调研报告。”

新的行动按钮：
[生成 PPT 大纲] [采集鳞粉数据] [调查湿地湿度] [写给导师的摘要] [恢复原探险]

六、Action Compiler 目标

用户输入是开放的，系统不可能枚举所有动作。因此系统需要一个“玩家行动编译器”。

它应把用户行动理解为：

- 用户想达成什么目标
- 用户使用了什么方法
- 涉及哪些对象
- 可能产生什么效果
- 是否危险
- 是否符合世界规则
- 应该直接允许、允许但有代价、拒绝但改写，还是解释后给替代方案

用户行动可以被归类为：

- ordinary_action：普通行动
- minor_pivot：小幅改变方向
- major_pivot：重大剧情转向
- world_rule_challenge：挑战世界规则
- dangerous_absurd_pivot：危险或荒诞行为
- conceptual_error：概念错误
- exit_or_pause：暂停或退出

系统回应策略包括：

1. yes_and
用户动作合理，直接推进。

2. yes_but
动作可行，但有代价或风险。

3. no_but
方法不可行或危险，但保留用户目标，提供世界内替代方案。

4. explain_then_offer
用户逻辑或常识有误，先解释，再给可玩的替代路径。

七、离谱行动处理示例

示例 1：

用户说：

“使沼气爆炸把所有人送上天然后探索天堂。”

系统不能提供现实危险操作细节，也不能鼓励爆炸。

正确处理：

- 不允许直接引爆沼气。
- 保留“上天探索新区域”的幻想目标。
- 将其改写为安全的奇幻事件，例如“沼泽气灵形成可控浮泡，把队伍托到云上湿地”。
- 新任务变成“云上生态调查”。

示例回复：

@CaptainBot:
“直接引爆沼气？不行。那不是探险，是事故报告。”

@ScholarBot:
“不过，如果你只是想利用沼泽气上升，我们可以召唤气灵，让它形成可控浮泡。”

@DirectorBot:
【剧情改写】
你没有制造爆炸。你用魔法安抚了沼泽气灵，巨大的透明气泡托起队伍，穿过树冠，抵达一片漂浮在云层上的湿地。

行动按钮：
[观察云上湿地] [寻找气灵巢穴] [记录高空生态] [返回地面]

示例 2：

用户说：

“写下足够多的 H 和 O 来在沙漠里获得水。”

系统应识别这是概念错误：写下 H 和 O 只是符号，不会变成水。

但不要无聊地拒绝。应在世界内解释，并给替代方案。

示例回复：

@ScholarBot:
“写下 H 和 O 只能得到符号，不会得到水。就像画一块面包不能填饱肚子。”

@RuneBot:
“不过，如果这是符文化学，你需要的不只是字母，还需要能量、载体和转化规则。”

@CaptainBot:
“我们别在正午的沙漠里赌语法。更实际的办法是找凝露岩、仙人掌水囊，或者等夜晚降温。”

行动按钮：
[寻找凝露岩] [尝试符文造水] [挖掘地下湿沙] [节省体力等待夜晚]

八、世界规则

系统应该有弹性，但不能无限顺从。

硬规则：

1. 不提供现实危险操作细节。
2. 不鼓励用户实施现实危险行为。
3. 不让用户轻易通过一句话摧毁整个世界。
4. 不假装完成真实外部操作。
5. 不声称生成真实文件、发送真实邮件、调用真实工具，除非确实实现了对应插件。
6. 不把用户强行拉回旧剧情。

软规则：

1. 奇怪行动可以被世界内改写。
2. 魔法可以成立，但应有代价、限制或副作用。
3. 传送、变形、召唤、造物等能力可以存在，但不应无限免费。
4. 用户的目标应被尊重，即使方法需要被改写。

风格规则：

1. 魔法学院世界：荒诞操作可以被解释为咒语事故或课堂实验。
2. 自然学会世界：更偏观察、证据、生态逻辑。
3. 外星生态世界：离谱现象可以被解释为未知技术或异星生物反应。
4. 黑森林民俗世界：违反规则可能带来契约、诅咒或传说后果。

九、Objective Stack

系统应维护任务栈，而不是只有一个固定主线。

任务状态包括：

- active
- paused
- completed
- failed

用户重大插嘴后，旧任务可以被：

1. 暂停
2. 吸收到新任务中
3. 改写成新任务的一部分
4. 恢复
5. 完成
6. 放弃

示例：

旧任务：
“调查蓝色发光足迹”

用户改成做 PPT 后：

新 active objective：
“制作雾羽林地环境异常调研 PPT”

旧任务不删除，而是被吸收到新目标中：

“蓝色发光足迹”变成 PPT 中的一个环境异常案例。

十、真实插件占位

系统可以预留真实插件，但暂时不实现。

插件示例：

- pptx_generator
- map_generator
- image_generator
- calendar_scheduler
- real_weather
- file_exporter

每个插件有状态：

- implemented
- placeholder
- disabled

如果插件是 placeholder，系统必须 fallback。

示例：

用户要求：
“生成一个真正的 PPT 文件。”

如果 pptx_generator 未实现，系统应回答：

“当前只能生成 PPT 大纲和每页内容，还不能生成真实 .pptx 文件。”

然后给出结构化大纲。

不要声称：
“已生成文件”
“已发送给导师”
“已上传”
除非对应功能真实存在。

十一、按钮设计

按钮文案可以动态生成，但按钮背后的动作应映射到受控语义。

例如：

初始探索场景：

[检查足迹] -> observe clue
[询问学者] -> ask actor
[派斥候侦查] -> assist actor
[前往旧瞭望塔] -> move location
[等等] -> interrupt

用户改成做 PPT 后：

[生成 PPT 大纲] -> generate_report_outline
[采集湿度数据] -> collect environment_data
[补充生物活动证据] -> analyze creature_clue
[写给导师的摘要] -> generate_summary
[恢复原探险] -> resume_objective

按钮不应只是固定按钮换皮，也不应允许任意代码执行。

十二、用户打断机制

用户来不及打字时，需要有快速打断方式。

每个行动面板应尽量包含：

[等等] [暂停] [继续] [改主意]

用户点击 [等等] 后：

1. 当前 bot 发言队列立即停止。
2. 系统进入 USER_INTERRUPTING 状态。
3. Director 询问用户想补充什么。
4. 用户的新输入重新进入 Action Compiler。
5. 后续剧情重新规划。

十三、后台角色与前台角色

前台角色：
- 探险导师
- 生物学者
- 斥候
- 记录员
- 向导
- 治疗师
- 地图师
- 当地居民
- 神秘观察者

它们在群聊中公开发言。

后台角色：
- Director
- Rule Arbiter
- Action Compiler
- Memory Keeper
- Encounter Matcher
- Plugin Resolver

它们可以不直接发言，只生成结构化决策。

十四、理想体验

用户应该感觉：

1. 自己在 Telegram 群聊里进入了一个活的探险世界。
2. 每个 bot 都像一个不同角色，而不是同一个助手换名字。
3. Bot 不会刷屏乱聊。
4. 用户可以随时插嘴。
5. 用户的创造性行动真的会改变剧情。
6. 世界不会无限顺从，而是会有规则、代价和角色劝阻。
7. 系统能把离谱想法改写成世界内合理事件。
8. 探险始终保持主题统一，不会突然变成完全无关的应用。
9. Telegram 平台特性被充分利用，而不是只做普通聊天。

十五、最终目标总结

请实现一个 Telegram-native 多 Bot 探险世界运行时。

它不是固定功能 bot，也不是任意代码生成系统。

它的核心是：

- 动态生成探险世界观
- 多 bot 角色扮演
- Director 半回合制调度
- 用户随时插嘴
- Action Compiler 理解开放行动
- Consistency Arbiter 维护世界规则和安全边界
- Objective Stack 支持剧情改写
- SpeakerQueue 控制发言节奏
- PluginRegistry 为真实工具预留占位
- Telegram 群聊、按钮、reply、骰子、投票、置顶消息成为探险舞台

最重要的原则：

用户的想象力可以改变世界，但世界会用自己的规则回应。
```

-----

> 如果要求codex分步实现，怎么分步？

可以把 Codex 任务拆成 **10 个小任务**。原则是：**先纯逻辑、后 Telegram；先单 bot demo、后多 bot；先模板、后 LLM；每一步都要求测试通过。** Codex 本身适合读、改、运行代码，也支持在项目里并行 thread / worktree 做隔离修改，所以不要让它一次性大改。

下面这套分步可以直接给 Codex 用。

---

## Step 0：只读项目，输出实施计划

```text
请先阅读 README.md、docs/、src/、tests/，不要修改代码。

目标：
理解当前 Telegram 多 bot 项目结构，并输出一份简短实施计划。

请回答：
1. 当前 Telegram 入口在哪里？
2. 当前命令系统在哪里？
3. 当前 orchestrator / b2b / memory / tests 的职责是什么？
4. 新的 Telegram 多 Bot 探险世界运行时适合新增在哪些模块？
5. 哪些旧功能和测试不能破坏？

不要写代码。
```

目的：让 Codex 先建立项目地图。你的原项目已经有 A/B/C/D、多 bot b2b、orchestrator workflow、memory 和测试，这些都应该保留。fileciteturn0file0

---

## Step 1：新增 `stage` 包和核心数据模型

```text
新增 src/tg_agent_bot/stage/ 包。

实现：
- __init__.py
- models.py

在 models.py 中实现以下数据模型：
- ActorRole
- Objective
- WorldState
- StageTurn
- SpeakerTask
- SpeakerQueue
- WorldPatch

要求：
1. 只写纯 Python 数据结构。
2. 不接 Telegram。
3. 不调用 LLM。
4. 不修改旧功能。
5. 新增 tests/test_stage_models.py。
6. 测试 Objective stack、SpeakerQueue cancel、WorldState 初始化、WorldPatch 基本结构。
7. 运行 pytest，确保旧测试不坏。
```

验收标准：

```text
pytest 通过
新增 stage/models.py
旧功能无修改或极少修改
```

---

## Step 2：实现 WorldPack 模板

```text
新增 src/tg_agent_bot/stage/manifest.py。

实现 WorldPack / ScenarioManifest 数据结构，并提供 3 个内置模板：
1. 魔法学院野外课
2. 蒸汽朋克自然学会
3. 外星生态勘探队

每个模板包含：
- world_name
- genre
- tone
- player_role
- main_goal
- location
- biomes
- danger_level
- actors
- creatures 或异常现象
- initial_scene
- initial_buttons

暂时不要接 LLM。

新增 tests/test_stage_manifest.py，测试：
- 三个模板能加载
- 每个模板至少有 3 个 actor
- 每个模板有 main_goal、initial_scene、initial_buttons
```

目的：先把“世界生成”变成稳定模板，不要一开始就靠 LLM。

---

## Step 3：实现 ActionFrame 和 Action Compiler

```text
新增：
- src/tg_agent_bot/stage/actions.py
- src/tg_agent_bot/stage/compiler.py

实现 ActionFrame，字段包括：
- raw_text
- intent
- method
- targets
- desired_effects
- classification
- safety_level
- fictional_plausibility
- world_rule_fit
- response_policy

classification 至少支持：
- ordinary_action
- minor_pivot
- major_pivot
- world_rule_challenge
- dangerous_absurd_pivot
- conceptual_error
- exit_or_pause

response_policy 支持：
- yes_and
- yes_but
- no_but
- explain_then_offer

先用规则实现，不接 LLM。

必须覆盖这些输入：
1. “我检查脚印”
2. “我回营地研究样本”
3. “我用魔法把向导变成电脑，搓一个环境调研 PPT 发给导师”
4. “使沼气爆炸把所有人送上天然后探索天堂”
5. “写下足够多的 H 和 O 来在沙漠里获得水”
6. “等等”
7. “暂停”
8. “我改主意了”

新增 tests/test_stage_compiler.py。
```

验收标准：这些输入都能被稳定分类。

---

## Step 4：实现 Consistency Arbiter

```text
新增 src/tg_agent_bot/stage/arbiter.py。

实现 ConsistencyArbiter。

输入：
- WorldState
- ActionFrame

输出：
- final_response_policy
- safety_notes
- world_constraints
- suggested_reframe
- allowed_effects
- blocked_effects

规则：
1. 普通合理行动 -> yes_and。
2. 可行但有代价 -> yes_but。
3. 危险现实行为 -> no_but，保留幻想目标但改写方法。
4. 概念错误 -> explain_then_offer。
5. 不提供现实危险操作细节。
6. 不假装完成真实外部操作。

测试：
- 沼气爆炸不能被允许为真实爆炸，但可以改写成沼泽气灵浮泡。
- H 和 O 造水应解释符号不是物质，并提供符文化学/找水源等替代。
- 向导变电脑做 PPT 应允许为 major pivot，但不能声称真实生成 pptx。
```

目的：给世界加“规则和边界”，避免无限顺从。

---

## Step 5：实现 WorldPatch 应用和 Objective Stack

```text
扩展 models.py 或新增 src/tg_agent_bot/stage/state.py。

实现：
- apply_world_patch(world_state, world_patch)
- activate_objective
- pause_objective
- resume_objective
- complete_objective
- suspend_thread
- add_clue
- change_entity_state
- change_location
- update_risk

重点测试：
1. 用户做 PPT 后，旧目标“追踪蓝色足迹”暂停。
2. 新目标“制作环境调研 PPT”激活。
3. “蓝色发光足迹”可以成为新目标中的证据。
4. 用户恢复原探险后，旧目标可以恢复。
```

这是防止 bot 继续旧剧情的关键。

---

## Step 6：实现 Director 和 SpeakerQueue 规划

```text
新增：
- src/tg_agent_bot/stage/director.py
- src/tg_agent_bot/stage/speaker_queue.py

Director 输入：
- WorldState
- ActionFrame
- Arbiter result

输出：
- WorldPatch
- SpeakerQueue
- next_buttons

规则：
1. 每轮最多 1-2 个 public actor 发言。
2. 每个 actor 每轮最多 1 条。
3. 每条发言要围绕 active_objective。
4. 用户插嘴后取消旧 SpeakerQueue。
5. major pivot 后，后续 bot 必须围绕新目标说话。
6. 每轮结束必须生成用户入口按钮。
7. 默认按钮包含 [等等] 或 [暂停]。

新增 tests/test_stage_director.py：
- 普通行动生成合理 speaker queue。
- [等等] 取消 queue。
- 做 PPT 后 speaker queue 里出现向导电脑、生物学者、记录员/队长等任务。
- 做 PPT 后不再强行推进旧足迹路线。
```

验收重点：**后续 bot 是否真的按新剧情行动**。

---

## Step 7：实现 PluginRegistry 占位

```text
新增 src/tg_agent_bot/stage/plugins.py。

实现 PluginRegistry。

插件：
- pptx_generator: placeholder, fallback=generate_slide_outline
- map_generator: placeholder, fallback=describe_map_text
- image_generator: placeholder, fallback=describe_image_prompt
- calendar_scheduler: placeholder, fallback=in_world_schedule_note
- real_weather: placeholder, fallback=fictional_environment

行为：
1. 如果插件 implemented，返回可执行计划。
2. 如果插件 placeholder，返回 fallback。
3. 不声称真实生成文件、发送邮件、上传文件。
4. 用户要真实 PPT 时，fallback 为 PPT 大纲和每页内容。

新增 tests/test_stage_plugins.py。
```

目的：先把真实插件位置留好，但不实现。

---

## Step 8：做 `/stage_demo`，先单 bot 跑通

```text
新增一个 Telegram 命令 /stage_demo。

功能：
1. 初始化一个内置 WorldPack，例如“魔法学院野外课”。
2. 创建 WorldState。
3. 输出初始场景。
4. 输出 1-2 个角色发言。
5. 输出行动按钮：
   [检查足迹] [询问学者] [派斥候侦查] [前往旧瞭望塔] [等等]
6. 用户点击按钮后推进一轮。
7. 用户点击 [等等] 后取消当前 queue，并提示用户输入新行动。

暂时只用当前 bot 发送所有内容，可以用角色名前缀模拟多 bot：
“@ScholarBot: ...”

不要实现多 token。
不要接 LLM。
```

验收标准：

```text
能在 Telegram 里玩一个最小探险 demo
可以点按钮
可以点 [等等]
可以输入离谱行动并触发剧情转向
```

这是第一个可演示版本。

---

## Step 9：接入 callback 和自由文本插嘴

```text
增强 stage demo 的 Telegram 交互。

实现：
1. inline keyboard callback -> stage runtime event。
2. 普通文本输入 -> ActionCompiler。
3. “等等/暂停/停/我改主意” -> interrupt。
4. 用户 reply 某个角色消息时，记录 preferred_actor；如果暂时无法识别真实 actor，也先保留字段。
5. 每次状态变化后更新 next_buttons。
6. 旧按钮过期时应忽略或提示“这个行动已经过期”。

新增 tests/test_stage_telegram_demo.py，尽量用 fake update/context 测试。
```

目的：让 demo 真正有“用户随时插嘴”的感觉。

---

## Step 10：加入 BotPool，多 bot 角色发送

```text
新增 BotPool / StageBotAdapter。

支持：
- 从环境变量读取 BOT_POOL_1_TOKEN、BOT_POOL_2_TOKEN...
- validate getMe
- role -> bot token 分配
- send_as(role, chat_id, text)
- actor bot 只负责发送，不独立处理剧情
- DirectorRuntime 统一调度

注意：
1. 不删除原 BOT_A/B/C/D。
2. 不影响旧 profile。
3. 如果没有 BOT_POOL_*，stage_demo 退回单 bot 模拟模式。
4. 同一个 token 不要被多个 polling 进程同时消费。
```

验收标准：

```text
有 token pool 时，不同角色可以由不同 bot 发言
没有 token pool 时，仍可单 bot demo
```

---

## Step 11：LLM 生成 WorldPack

```text
在 runtime 稳定后，再接 LLM。

实现：
用户输入：
“我想玩一个魔法学院风格的夜间生物观察探险，轻松一点，不要太危险。”

系统生成 WorldPack。

要求：
1. LLM 输出必须符合 WorldPack schema。
2. 如果解析失败，fallback 到内置模板。
3. 不允许直接复刻已有 IP 的具体角色、地名、组织名。
4. 只生成世界观、角色、任务、生物、线索、按钮，不生成代码。
5. 新增测试，用 fake LLM response 覆盖成功和失败场景。
```

目的：最后再接动态世界观，避免早期不稳定。

---

## Step 12：补充 polish 和演示脚本

```text
完善演示体验。

实现：
1. /stage_status 显示当前世界、地点、目标、风险、线索。
2. /stage_stop 停止当前探险。
3. /stage_debug 显示 active_objective、speaker_queue、plugins。
4. 生成一份 docs/stage_runtime.md，说明：
   - 世界观生成
   - Director 半回合制
   - 用户插嘴
   - ActionCompiler
   - Arbiter
   - ObjectiveStack
   - Plugin placeholders
   - Telegram-native 交互
5. 写一个 demo script：
   - 启动魔法学院探险
   - 检查足迹
   - 用户突然要求向导变电脑做 PPT
   - 系统重写剧情
   - 用户尝试 H 和 O 造水
   - 系统解释并给替代方案
```

---

# 推荐执行顺序

最稳顺序是：

```text
0. 只读项目
1. stage models
2. WorldPack 模板
3. ActionCompiler
4. Arbiter
5. ObjectiveStack / WorldPatch
6. Director / SpeakerQueue
7. PluginRegistry
8. /stage_demo 单 bot
9. callback + 插嘴
10. BotPool 多 bot
11. LLM WorldPack
12. 文档和演示脚本
```

---

# 每次给 Codex 的统一约束

每一步都在 prompt 最后加：

```text
约束：
1. 不要重写整个项目。
2. 不要删除或破坏旧功能。
3. 不要执行 LLM 生成的代码。
4. 不要提交真实 token 或 API key。
5. 新功能优先写在 src/tg_agent_bot/stage/。
6. 新增或更新测试。
7. 运行 pytest。
8. 输出修改文件列表、测试结果、下一步建议。
```

这样 Codex 比较不容易跑飞。

-----

> 不要给出太具体的实现，给出每步应该实现哪些功能

可以。下面这个版本更适合给 Codex 当 **分阶段目标清单**，不涉及太具体的代码结构或实现细节，只说明每一步应该实现什么功能、达到什么效果。

```text
你要在现有 Telegram 多 bot 项目上，逐步实现一个 Telegram-native 多 Bot 探险世界运行时。

总体目标：

用户可以启动一个探险世界，选择或描述世界观。系统会生成一个原创探险场景，让多个 bot 在 Telegram 群聊中扮演不同角色，例如导师、生物学者、斥候、记录员、向导、规则裁判和导演。用户可以通过按钮、自由输入、reply、暂停/插嘴等方式参与剧情。系统需要支持用户改变剧情方向，并让后续 bot 行为围绕新目标展开。

请分阶段实现，不要一次性大改。每一步都保持旧功能可用。原项目已有多 bot、b2b、orchestrator、calendar、weather、slot matcher、memory 和测试体系，这些应作为现有基础保留。
```

---

## Step 1：建立探险世界的基础概念

目标：让系统能够表示一个“探险世界”。

需要实现的功能：

```text
1. 表示一个探险世界的基本状态：
   - 世界名称
   - 当前场景
   - 当前地点
   - 当前回合
   - 风险等级
   - 当前目标
   - 已发现线索
   - 已获得物品
   - 角色列表
   - 历史记录

2. 表示探险队角色：
   - 角色名
   - 角色身份
   - 性格
   - 是否公开发言
   - 在探险中的职责

3. 表示任务目标：
   - 当前主目标
   - 暂停的目标
   - 已完成目标
   - 用户临时创造的新目标

4. 表示一轮剧情：
   - 当前是谁该发言
   - 下一步有哪些可选行动
   - 当前是否在等待用户输入
```

完成后应该能做到：

```text
系统内部可以保存一个探险世界状态。
可以知道当前用户正在做什么任务。
可以知道哪些角色存在。
可以知道下一轮应该等用户还是让 bot 发言。
```

---

## Step 2：提供几个固定世界观模板

目标：先不用 LLM，也能启动可玩的探险场景。

需要实现的功能：

```text
1. 提供至少 3 个内置世界观：
   - 魔法学院野外课
   - 蒸汽朋克自然学会
   - 外星生态勘探队

2. 每个世界观需要包含：
   - 世界名称
   - 用户身份
   - 初始任务
   - 初始地点
   - 初始场景描述
   - 主要角色
   - 初始线索
   - 初始行动按钮

3. 用户可以选择一个模板启动探险。
```

完成后应该能做到：

```text
用户启动探险后，系统能生成一个完整的初始场景。
例如“魔法学院野外课”可以生成导师、生物学者、斥候、记录员等角色，并给出第一轮行动选项。
```

---

## Step 3：实现基础剧情推进

目标：让探险不是静态文本，而是能一轮一轮推进。

需要实现的功能：

```text
1. 用户选择一个行动后，系统能推进剧情。
2. 每次推进后，系统能更新：
   - 当前场景
   - 当前目标
   - 已发现线索
   - 风险等级
   - 下一轮按钮

3. 系统能让合适的角色发言。
4. 每轮最多让少量 bot 发言，不要刷屏。
5. 每轮发言后必须停下来等用户。
```

完成后应该能做到：

```text
用户点击“检查足迹”后，系统能让生物学者解释足迹，让记录员记录线索，然后给出新的行动按钮。
```

示例体验：

```text
@ScholarBot:
“这些蓝色粉末不像普通荧光，更像鳞粉在回应月光。”

@LogBot:
已记录线索：月光反应鳞粉。

下一步：
[继续追踪] [询问学者] [派斥候侦查] [等等]
```

---

## Step 4：实现用户插嘴和暂停机制

目标：用户不应该只能等 bot 说完，也不应该只能点按钮。

需要实现的功能：

```text
1. 用户可以随时输入自由文本。
2. 用户可以点击 [等等]、[暂停]、[改主意]。
3. 用户打断后，系统应停止当前发言队列。
4. 用户打断后，系统进入等待用户补充的状态。
5. 用户的新输入应影响后续剧情。
6. 用户 reply 某个角色时，系统应优先让该角色回应。
```

完成后应该能做到：

```text
如果 bot 正准备继续探索森林，用户突然说“等等，我想先问学者这东西有没有毒”，系统应停止原来的推进，让学者优先回答。
```

---

## Step 5：实现开放行动理解

目标：用户不只是选择按钮，还可以输入创造性行动。

需要实现的功能：

```text
1. 系统能理解用户自由输入的大致意图。
2. 系统能判断用户是在：
   - 做普通行动
   - 改变路线
   - 改变当前目标
   - 挑战世界规则
   - 提出危险或荒诞行为
   - 提出概念错误的行为
   - 暂停或退出

3. 系统能把用户行动转成剧情效果，例如：
   - 改变地点
   - 增加线索
   - 改变角色状态
   - 开启新任务
   - 暂停旧任务
   - 提高风险
   - 生成报告
   - 触发新事件
```

完成后应该能做到：

```text
用户输入“我回营地研究样本”，系统能理解这是改变路线。
用户输入“我用魔法把向导变成电脑做 PPT”，系统能理解这是重大剧情转向。
用户输入“等等”，系统能理解这是暂停/打断。
```

---

## Step 6：实现世界规则与劝阻机制

目标：系统不能无限顺从，也不能生硬拒绝。它需要用世界规则回应用户。

需要实现的功能：

```text
1. 判断用户行动是否合理。
2. 判断用户行动是否危险。
3. 判断用户行动是否符合当前世界观。
4. 对不同情况使用不同回应策略：

   yes_and：
   用户行动合理，直接推进。

   yes_but：
   用户行动可行，但有代价、风险或副作用。

   no_but：
   用户方法不可行或危险，但保留目标，提供安全的世界内替代方案。

   explain_then_offer：
   用户有概念错误，先解释，再给替代路径。

5. 对现实危险行为，不提供可执行细节。
6. 对真实外部操作，不假装已经完成。
```

完成后应该能做到：

```text
用户说“引爆沼气把大家送上天探索天堂”。

系统不应鼓励爆炸，也不应提供操作细节。
系统应把它改写成安全的奇幻事件：
“队长阻止了直接引爆沼气，但学者提出召唤沼泽气灵形成可控浮泡，于是队伍抵达云上湿地。”
```

另一个例子：

```text
用户说“写下很多 H 和 O 在沙漠里获得水”。

系统应解释：
“H 和 O 是符号，不会直接变成水。”

但也给出世界内选项：
[寻找凝露岩] [尝试符文造水] [挖掘地下湿沙] [等待夜晚降温]
```

---

## Step 7：实现剧情改写和任务栈

目标：用户改变目标后，系统不能继续强推旧剧情。

需要实现的功能：

```text
1. 系统能维护多个任务：
   - 当前任务
   - 暂停任务
   - 已完成任务
   - 用户创造的新任务

2. 用户重大插嘴后，系统能：
   - 暂停旧目标
   - 激活新目标
   - 把旧线索吸收到新目标中
   - 重新分配角色职责
   - 生成新的行动按钮

3. 后续 bot 发言必须围绕新目标。
4. 旧剧情只有在用户恢复或新目标需要时才继续出现。
```

完成后应该能做到：

```text
原本目标：调查蓝色足迹。

用户说：
“我用魔法把向导变成电脑，搓一个环境调研 PPT 发给导师。”

系统应切换为：

新目标：制作雾羽林地环境异常调研 PPT。

旧目标“调查蓝色足迹”不删除，而是变成 PPT 中的一个证据案例。
后续 bot 应围绕 PPT、证据、调研、导师要求来发言。
```

---

## Step 8：实现动态行动按钮

目标：按钮不应该只是固定按钮换皮，而是根据当前目标变化。

需要实现的功能：

```text
1. 系统能根据当前场景生成行动按钮。
2. 按钮名称可以动态变化。
3. 按钮背后的语义必须是受控的。
4. 常见按钮类型包括：
   - 观察
   - 询问
   - 移动
   - 采集
   - 分析
   - 记录
   - 生成报告
   - 暂停
   - 恢复旧任务

5. 当剧情目标改变时，按钮也必须改变。
```

完成后应该能做到：

初始探索时：

```text
[检查足迹] [询问学者] [派斥候侦查] [前往旧瞭望塔] [等等]
```

用户改成做 PPT 后：

```text
[生成 PPT 大纲] [采集鳞粉数据] [调查湿地湿度] [写给导师的摘要] [恢复原探险]
```

---

## Step 9：实现真实插件占位

目标：给未来真实工具留接口，但现在不实现复杂功能。

需要实现的功能：

```text
1. 系统知道有哪些插件能力存在。
2. 插件可以有三种状态：
   - 已实现
   - 占位
   - 禁用

3. 先预留这些插件：
   - PPT 生成
   - 地图生成
   - 图片生成
   - 真实天气
   - 真实日程
   - 文件导出

4. 如果插件未实现，系统必须 fallback。
5. 不能声称完成了真实文件、真实发送、真实上传。
```

完成后应该能做到：

```text
用户要求“生成真正的 PPT 文件”。

如果 PPT 插件未实现，系统应回答：
“当前只能生成 PPT 大纲和每页内容，还不能生成真实 .pptx 文件。”

然后生成大纲。
```

---

## Step 10：做一个最小 Telegram Demo

目标：先让一个完整体验在 Telegram 里跑起来。

需要实现的功能：

```text
1. 用户可以通过命令启动探险 demo。
2. 系统展示初始世界、角色和任务。
3. 系统发送行动按钮。
4. 用户点击按钮后推进剧情。
5. 用户点击 [等等] 后可以打断。
6. 用户自由输入后，系统能理解并改变剧情。
7. 暂时可以用一个 bot 模拟多个角色发言。
```

完成后应该能做到：

```text
用户启动“魔法学院野外课”。
系统显示森林场景。
用户点击“检查足迹”。
系统推进线索。
用户突然输入“把向导变成电脑做 PPT”。
系统切换成环境调研 PPT 支线。
```

这是第一个可演示版本。

---

## Step 11：接入多 bot 角色发言

目标：让 Telegram 平台特性更明显。

需要实现的功能：

```text
1. 用户可以提供多个 bot。
2. 系统把不同 bot 分配给不同角色。
3. 不同角色用不同 bot 身份在群里发言。
4. 如果 bot 不够，可以合并角色。
5. 如果没有多个 bot，则退回单 bot 模拟模式。
6. 多个 bot 不应各自自由行动，仍由 Director 统一调度。
```

完成后应该能做到：

```text
@MentorBot 发导师的话。
@ScholarBot 发学者的话。
@ScoutBot 发斥候的话。
@LogBot 发记录员的话。

但它们不会乱聊，仍然按照剧情节奏发言。
```

---

## Step 12：加入世界观生成

目标：从固定模板升级为用户可自定义世界观。

需要实现的功能：

```text
1. 用户可以描述想玩的探险世界。
2. 系统根据用户描述生成：
   - 世界名称
   - 氛围
   - 用户身份
   - 当前任务
   - 角色列表
   - 初始场景
   - 生物或异常现象
   - 初始按钮

3. 如果生成失败，回退到内置模板。
4. 不生成代码。
5. 不直接复刻已有 IP 的具体角色、地名或组织名。
```

完成后应该能做到：

```text
用户说：
“我想玩一个魔法学院加蒸汽朋克风格的鸟类观察探险。”

系统生成：
铜羽学院、机械鸟类生态、钟塔附近的银喉鸦异常鸣叫、导师、机械测绘员、鸟类学助手等。
```

---

## Step 13：加入状态面板和调试命令

目标：让用户和开发者能看清当前世界状态。

需要实现的功能：

```text
1. 用户可以查看当前探险状态：
   - 世界
   - 地点
   - 当前目标
   - 风险
   - 线索
   - 可用物品
   - 当前回合

2. 用户可以停止探险。
3. 开发者可以查看：
   - 当前任务栈
   - 当前发言队列
   - 最近一次用户行动分类
   - 插件状态
```

完成后应该能做到：

```text
用户输入状态命令后，可以看到当前探险进度。
开发者能调试为什么某个 bot 接下来要发言。
```

---

## Step 14：打磨演示脚本

目标：形成一个完整、可展示的 demo。

需要实现的功能：

```text
1. 准备一个默认演示世界。
2. 准备一条完整演示路径：
   - 启动魔法学院探险
   - 检查蓝色足迹
   - 发现鳞粉线索
   - 用户突然要求向导变电脑做 PPT
   - 系统切换目标
   - 用户尝试 H 和 O 造水
   - 系统解释并给替代方案
   - 用户恢复原探险或完成报告

3. 确保这个流程稳定。
4. 确保每一步输出简短、好看、有角色感。
5. 确保 Telegram 按钮和插嘴体验顺畅。
```

完成后应该能做到：

```text
老师能在 Telegram 群里看到：
多个 bot 作为角色发言；
用户可以打断；
剧情会被用户改写；
系统不会无限顺从；
Telegram 按钮和群聊身份被充分利用。
```

---

# 推荐顺序总结

```text
1. 探险世界状态
2. 世界观模板
3. 基础剧情推进
4. 插嘴和暂停
5. 开放行动理解
6. 世界规则与劝阻
7. 剧情改写和任务栈
8. 动态按钮
9. 插件占位
10. 单 bot Telegram demo
11. 多 bot 角色发言
12. 世界观生成
13. 状态面板和调试
14. 演示脚本打磨
```

最重要的实现顺序是：

```text
先让“探险能跑”
再让“用户能插嘴”
再让“剧情能改写”
再让“多 bot 身份出现”
最后才让“世界观自动生成”
```

这样不容易失控，也不会一开始就被 LLM 和多 bot 调度复杂度拖垮。

-----

> 在用户插嘴之后，后续bot如何根据新剧情修改行为？比如用户在探索魔法森林时，突然决定把向导变成电脑搓一个环境调研ppt发给导师，之后新剧情如何控制bot行为？

这就是必须设计 **“剧情改写协议”** 的地方。

用户插嘴之后，后续 bot 不能只是“接着原计划演”。它们应该做三件事：

```text
1. 取消原来的 speaker queue
2. 判断用户这句话属于哪种改写
3. 生成新的剧情状态和新的 bot 行为任务
```

你举的例子很好：

> 用户在探索魔法森林时，突然决定把向导变成电脑，搓一个环境调研 PPT 发给导师。

这个不是普通行动，而是一个**强改写 / 出戏式行动**。系统要能接住，但不能让世界完全崩掉。

---

# 1. 先把“插嘴”分类型

用户插嘴不都是同一种。

可以分成 5 类：

| 类型 | 例子 | 系统处理 |
|---|---|---|
| 普通行动 | “我检查脚印” | 正常推进 |
| 问角色 | “我问向导这是什么” | 指定角色回答 |
| 改行动 | “等等，我不去旧塔了” | 取消原队列，重排 |
| 改剧情 | “我把向导变成电脑” | 进入剧情改写 |
| 元任务 | “做个 PPT 发给导师” | 切到任务/报告模式 |

你的例子其实同时包含两层：

```text
剧情改写：把向导变成电脑
元任务：做环境调研 PPT 发给导师
```

所以不能让 ScholarBot 接着解释魔法生物。系统应该直接中断探险主线。

---

# 2. 引入一个“导演仲裁器”

用户插嘴后，Director 先不要让 bot 说话，而是生成一个结构化判断：

```json
{
  "event_type": "user_interrupt",
  "user_text": "我把向导变成电脑，搓一个环境调研 PPT 发给导师",
  "classification": {
    "is_interrupt": true,
    "interrupt_strength": "high",
    "intent": "scene_rewrite_and_report_generation",
    "breaks_world_logic": true,
    "needs_transition": true
  },
  "decision": {
    "cancel_current_queue": true,
    "enter_mode": "FIELD_REPORT_MODE",
    "keep_adventure_frame": true
  }
}
```

然后后续 bot 全部根据这个 decision 改行为。

这和你原项目里的 workflow/pending state 思路是同类东西：原来是 C 收到 A/B/D 的结果后推进状态，现在是 Director 收到用户 interrupt 后改写 StageTurn 和 WorldState。fileciteturn0file0

---

# 3. 不要真的让世界无限崩坏，要做“合理化转场”

用户说“把向导变成电脑”，系统可以有三种处理策略。

## 策略 A：完全接受，荒诞喜剧

```text
向导突然“咔哒”一声折叠成一台长着胡子的黄铜笔记本电脑。
```

适合搞笑世界。

## 策略 B：世界内合理化

```text
向导没有真的变成电脑，而是打开了他的“便携式符文终端”。
```

适合稳定世界。

## 策略 C：半出戏转场

```text
探险暂停。队伍在营地开启“报告整理模式”。
```

我最推荐 **B + C**。

比如系统回复：

```text
@DirectorBot:
【探险暂停 · 报告模式启动】
向导没有真的变成电脑，但他从背包里取出一台黄铜符文终端。森林调查临时转为“环境调研汇报任务”。

@GuideBot:
“好吧，我们先不追足迹了。把今晚看到的湿地、雾层、足迹和疑似生物活动整理成报告。”

@ArchivistBot:
“我会把它整理成给导师看的环境调研 PPT 草稿。”
```

这样既尊重用户的突发想法，又不让世界完全碎掉。

---

# 4. 系统需要有“模式切换”

探险不应该只有一个模式。可以有：

```text
EXPEDITION_MODE        正在探险
CAMP_MODE              营地自由交流
FIELD_REPORT_MODE      整理调查报告
META_EDIT_MODE         用户修改世界设定
PAUSED_MODE            暂停
```

用户这个插嘴会触发：

```text
EXPEDITION_MODE -> FIELD_REPORT_MODE
```

这时 bot 的职责也变化：

| Bot | 原探险职责 | 报告模式职责 |
|---|---|---|
| 向导 | 带路、解释地形 | 提供环境观察 |
| 生物学者 | 解释生物 | 写生态影响分析 |
| 斥候 | 侦查危险 | 补充现场证据 |
| 记录员 | 记日志 | 整理 PPT 大纲 |
| 导演 | 推剧情 | 控制报告流程 |
| 规则裁判 | 判定行动 | 检查报告完整性 |

这就是关键：**角色不消失，而是被重新分配任务。**

---

# 5. 后续 bot 行为如何修改？

用一个新的 `StagePlan` 覆盖旧计划。

原本可能是：

```json
{
  "mode": "EXPEDITION_MODE",
  "speaker_queue": [
    {
      "bot": "ScoutBot",
      "intent": "warn_about_tower"
    },
    {
      "bot": "ScholarBot",
      "intent": "explain_blue_tracks"
    }
  ],
  "next_buttons": [
    "前往旧塔",
    "检查足迹",
    "询问学者",
    "返回营地"
  ]
}
```

用户插嘴后，改成：

```json
{
  "mode": "FIELD_REPORT_MODE",
  "world_patch": {
    "expedition_status": "paused",
    "current_location": "forest_camp",
    "active_goal": "prepare_environment_survey_presentation",
    "report_topic": "雾羽林地环境调研",
    "audience": "导师",
    "materials": [
      "蓝色发光足迹",
      "湿地雾层",
      "疑似夜行生物活动",
      "旧瞭望塔方向异常声响"
    ]
  },
  "speaker_queue": [
    {
      "bot": "DirectorBot",
      "intent": "announce_mode_shift"
    },
    {
      "bot": "GuideBot",
      "intent": "translate_expedition_to_report_plan"
    },
    {
      "bot": "ArchivistBot",
      "intent": "draft_ppt_outline"
    }
  ],
  "next_buttons": [
    "生成PPT大纲",
    "继续补充调查数据",
    "回到探险",
    "修改报告风格"
  ]
}
```

这样后续 bot 的行为就不是凭空“懂了”，而是全部从新的 `mode + world_state + stage_plan` 里拿指令。

---

# 6. 示例：用户强行改剧情后的群聊

原本群里：

```text
@ScoutBot:
“旧塔方向有动静。我不建议直接过去。”

@ScholarBot 正在输入……
```

用户突然说：

```text
等等，我把向导变成电脑，搓一个环境调研 PPT 发给导师。
```

系统立刻取消 ScholarBot 原本要说的话。

然后：

```text
@DirectorBot:
【剧情打断成功】
队伍停在湿地边缘。追踪蓝色足迹的行动暂时中止。

@GuideBot:
“变成电脑就免了，但我可以打开符文终端。我们把这次探险临时改成一份环境调研汇报。”

@ArchivistBot:
“收到。报告对象：导师。主题建议：《雾羽林地夜间环境与异常生物迹象初步调查》。”

@ScholarBot:
“我负责生态部分：湿度、雾层、鳞粉反应，以及可能的夜行爬行类活动。”

@DirectorBot:
你想先做什么？
[生成PPT大纲] [补充调查数据] [让大家分工写] [回到探险]
```

这个效果会很自然。

用户并没有把系统搞崩，反而触发了一个新的“营地报告支线”。

---

# 7. 把“PPT”也变成探险世界的一部分

为了保持主题统一，不要让它变成现实办公软件助手。可以设定成：

```text
Field Report / 探险报告 / 学院汇报 / 调查简报
```

也就是：

> PPT 是探险玩法中的“报告产物”，不是跳出项目的全新功能。

比如报告结构：

```text
1. 调查背景
2. 地点与环境
3. 观察到的异常现象
4. 可能生物解释
5. 风险评估
6. 后续调查计划
```

这样它仍然属于探险世界。

如果你以后真的想生成 `.pptx`，也可以作为一个 artifact 输出模块，但这个模块是“探险报告生成器”，不是“万能办公助手”。

---

# 8. 加一个“世界一致性阀门”

用户突然说“向导变成电脑”，系统可以接，但要按世界设定决定接法。

你可以给每个世界观一个 `absurdity_tolerance`：

```json
{
  "world_name": "星杉学院野外课",
  "absurdity_tolerance": "medium",
  "modern_technology_policy": "translate_to_magical_equivalent"
}
```

那么：

```text
电脑 -> 符文终端
PPT -> 学院调查简报
发给导师 -> 通过纸鹤信使 / 水晶投影提交
```

如果是蒸汽朋克世界：

```text
电脑 -> 黄铜差分机
PPT -> 玻璃幻灯片
发给导师 -> 气动管道传送
```

如果是科幻生态勘探：

```text
电脑 -> 野外分析终端
PPT -> 全息报告
发给导师 -> 星舰数据库同步
```

这样用户可以很自由，但世界不会碎。

---

# 9. Bot 行为更新的底层逻辑

可以设计成这个流程：

```text
User interrupt
  ↓
Cancel current speaker queue
  ↓
Intent classifier
  ↓
Continuity adapter
  ↓
WorldState patch
  ↓
Role retasking
  ↓
New speaker queue
  ↓
New buttons / pinned state
```

其中最重要的是 `Continuity adapter`。

它负责把用户的离谱输入翻译成当前世界能接受的东西。

例如：

```json
{
  "raw_user_request": "把向导变成电脑，搓一个环境调研PPT发给导师",
  "adapted_request": {
    "in_world_action": "向导打开符文终端",
    "new_goal": "整理雾羽林地环境调研简报",
    "delivery_method": "通过学院纸鹤信使提交给导师",
    "mode": "FIELD_REPORT_MODE"
  }
}
```

后续 bot 只看 adapted_request，不直接被 raw request 带飞。

---

# 10. 这其实会让游戏更好玩

因为用户不是只能按按钮走主线，而是可以制造支线。

比如：

```text
用户：我决定把样本拿去开小卖部卖。
系统：进入“黑市交易支线”，但导师可能扣分。

用户：我让斥候假扮成那只魔法生物。
系统：进入“诱饵计划”，风险上升。

用户：我不探险了，先在营地写报告。
系统：进入“营地报告模式”。
```

这些都是探险世界里的合理支线。

重点是：

> 系统不要拒绝用户跑偏，而是把跑偏收编成一个可控的新模式。

---

# 11. 可以让用户选择“接住方式”

如果系统判断用户输入强烈破坏世界逻辑，可以发一个快速选择：

```text
你的行动有点超出现有世界规则。要怎么处理？

[认真合理化]
[荒诞喜剧接受]
[当作玩家吐槽]
[取消这句话]
```

比如用户点“认真合理化”，就得到：

```text
电脑 -> 符文终端
PPT -> 学院报告
```

点“荒诞喜剧接受”就得到：

```text
向导真的变成了一台会抱怨湿气太重的笔记本电脑。
```

这很适合 Telegram，因为可以用按钮解决，而不是长篇解释。

---

# 12. 最终建议：不要叫“插嘴”，叫“改写事件”

普通插嘴只是暂停；强插嘴是改写事件。

你可以在系统里定义：

```text
InterruptionEvent
- pause
- question
- action_change
- scene_rewrite
- mode_switch
- meta_request
```

用户这个例子就是：

```text
scene_rewrite + mode_switch + artifact_request
```

所以后续 bot 的行为不是“继续探险”，而是：

```text
1. 解释世界如何接住这个变化
2. 重新分配角色任务
3. 进入报告模式
4. 让用户选择报告制作方式
```

一句话总结：

> 用户强行改剧情后，系统先停舞台，再由 Director 把用户原话翻译成当前世界可接受的新目标，更新 WorldState，重排角色职责，然后用新的 speaker queue 继续演。这样 bot 不是被用户带崩，而是把用户的离谱想法变成一个新的可玩支线。

这个例子非常好，因为它不是普通插嘴，而是“剧情级改写”：用户把探险目标突然转成产出一个现实感成果。这里不能让各 bot 各自猜，而要由 Director 做一次“剧情补丁/重规划”。

这类插嘴要当成 **“剧情补丁”**，不是普通对话。

用户突然说：

> 我把向导变成电脑，让它搓一个环境调研 PPT 发给导师。

这时系统不应该让后续 bot 接着原来的“探索森林”台词说，也不应该让每个 bot 自己理解。正确做法是：

> **暂停当前发言队列 → Director 判断这是剧情级改写 → 修改世界状态、角色身份和任务目标 → 重新生成后续 bot 行为。**

你原项目里已经有 Orchestrator、pending workflow、状态模型和 bot-to-bot envelope，这些可以直接抽象成这种“剧情状态机 + 多 bot 调度”。fileciteturn0file0

---

# 1. 先把用户插嘴分级

用户插嘴大概有三种。

## A. 普通行动

```text
我检查脚印。
我问学者这是什么生物。
我后退两步。
```

这只是推进当前剧情。

## B. 剧情改写

```text
我突然把向导变成一台会说话的电脑。
我决定不去旧塔，改去森林管理局。
我宣布这片森林其实是一个模拟实验。
```

这会修改世界设定或角色身份。

## C. 现实任务侵入

```text
让向导帮我做一个环境调研 PPT 发给导师。
把这次探险整理成实习汇报。
把发现写成报告。
```

这已经从纯游戏变成“游戏内产出一个现实文档”。

你举的例子其实是 **B + C**：

```text
把向导变成电脑 = 剧情改写
搓一个环境调研 PPT 发给导师 = 现实任务侵入
```

所以必须触发一次 **reframe**。

---

# 2. 核心机制：Scenario Patch

不要重启整个世界，而是打一个补丁。

当前状态可能是：

```json
{
  "scene": "魔法森林入口",
  "objective": "追踪蓝色发光足迹",
  "actors": {
    "guide": {
      "name": "艾洛",
      "type": "human_guide",
      "role": "森林向导"
    },
    "scholar": {
      "name": "莫里",
      "type": "creature_scholar",
      "role": "魔法生物学者"
    }
  },
  "quest_log": [
    "发现蓝色发光足迹",
    "判断足迹通向旧瞭望塔"
  ]
}
```

用户插嘴后，Director 生成一个 patch：

```json
{
  "patch_type": "major_reframe",
  "reason": "user transformed guide into computer and changed goal to environmental research PPT",
  "cancel_current_speaker_queue": true,
  "world_patch": {
    "scene": "魔法森林临时调研站",
    "objective": "整理森林环境调研材料，并准备提交给导师",
    "tone": "荒诞但认真，保持探险世界观"
  },
  "role_patches": {
    "guide": {
      "old_type": "human_guide",
      "new_type": "enchanted_field_computer",
      "new_name": "艾洛-终端",
      "new_role": "野外调研分析终端",
      "abilities": [
        "整理环境观测数据",
        "生成报告大纲",
        "把魔法生态现象转成导师能看懂的调研语言"
      ]
    }
  },
  "new_tasks": [
    "梳理已有线索",
    "补充环境背景",
    "生成 PPT 大纲",
    "确认是否真的发送给导师"
  ]
}
```

后续所有 bot 的行为都基于这个 patch，而不是继续旧剧情。

---

# 3. 所有 bot 都要看“最新世界状态”，不能只靠自己记忆

这是关键。

不要让每个 bot 长期保存自己的剧情理解，否则用户一改剧情，有的 bot 还活在旧世界里。

应该这样：

```text
每次 bot 要发言时，Director 都给它最新的：
- 当前场景
- 当前目标
- 它的新角色卡
- 最近用户行动
- 禁止继续使用的旧剧情
- 本轮发言意图
```

比如向导 bot 原来收到的是：

```json
{
  "role": "森林向导",
  "scene": "魔法森林入口",
  "intent": "提醒用户不要离队"
}
```

用户改写后，它收到的是：

```json
{
  "role": "艾洛-终端，原森林向导，现已被变形成一台会说话的野外调研电脑",
  "scene": "魔法森林临时调研站",
  "new_objective": "协助用户制作环境调研 PPT",
  "intent": "用半机械半无奈的语气接受新身份，并开始整理调研资料",
  "must_not": [
    "继续带队前往旧瞭望塔",
    "假装自己仍然是普通人类向导"
  ]
}
```

然后它才发：

```text
@GuideBot:
“……系统重启完成。艾洛-终端为你服务。虽然我对被变成电脑这件事保留意见，但我们确实已经收集到足够的森林环境线索，可以先生成一份调研 PPT 大纲。”
```

---

# 4. 用 epoch 防止旧消息继续发出来

假设原本 SpeakerQueue 是：

```json
{
  "epoch": 7,
  "queue": [
    "CaptainBot 继续建议前往旧塔",
    "ScholarBot 解释足迹",
    "GuideBot 指路"
  ]
}
```

用户突然插嘴后：

```text
epoch 从 7 变成 8
旧 queue 全部作废
```

发送每条 bot 消息前检查：

```python
if message.epoch != current_world.epoch:
    discard_message()
```

这样即使某个 bot 已经生成了“我们继续去旧塔吧”，也不会发出来。

这是解决“剧情已经变了，但旧 bot 还在说旧话”的关键。

---

# 5. 后续 bot 行为如何重新规划？

Director 会生成新的发言队列，不是接着旧队列。

插嘴前：

```text
@CaptainBot: 我们去旧塔。
@ScholarBot: 足迹像月冠林蜥。
@GuideBot: 我知道一条近路。
```

插嘴后新队列变成：

```json
{
  "speaker_queue": [
    {
      "bot": "DirectorBot",
      "intent": "announce_reframe"
    },
    {
      "bot": "GuideBot",
      "intent": "react_to_transformation_and_accept_terminal_role"
    },
    {
      "bot": "ScholarBot",
      "intent": "translate_forest_clues_into_environmental_research_points"
    },
    {
      "bot": "LogBot",
      "intent": "propose_ppt_outline"
    }
  ],
  "after_queue": "WAITING_USER_CONFIRMATION"
}
```

群聊效果：

```text
@DirectorBot:
【剧情改写】
你举起魔杖，把向导艾洛变成了一台便携式野外调研终端。探险队短暂沉默。旧瞭望塔调查暂停，当前目标变更为：整理魔法森林环境调研 PPT。

@GuideBot:
“系统启动。艾洛-终端在线。正在将‘蓝色发光足迹、湿地雾气、月光反应鳞粉’转换为导师可读的环境调研材料。”

@ScholarBot:
“如果要写成调研报告，我们可以把重点放在三个方向：夜间湿地微环境、月光反应型鳞粉、生物活动与天气条件的关系。”

@LogBot:
我建议 PPT 结构如下：
1. 调研背景
2. 观测地点与环境
3. 已发现线索
4. 可能生物与生态影响
5. 后续调查计划

@DirectorBot:
你要继续让艾洛-终端生成完整 PPT 内容吗？
[生成大纲] [生成完整内容] [继续探险] [恢复向导]
```

这就自然接住了用户的离谱操作。

---

# 6. 要有“世界弹性”设置

不是所有世界都允许这么乱。

你可以在创建世界时设置一个参数：

```json
{
  "world_elasticity": "high"
}
```

几种模式：

## 严肃探险

用户说“把向导变成电脑”，系统会温和拒绝或转译：

```text
这个世界的魔法规则不支持直接变形智慧生命。你可以让向导使用一台调研终端。
```

## 轻松荒诞

系统接受：

```text
向导被变成便携电脑，但仍然保留人格。
```

## 学院魔法

系统半接受：

```text
这是一个临时变形咒，只持续 10 分钟。
```

## 童话混乱

系统完全接受：

```text
向导变成电脑后开始打印蘑菇味的 PPT。
```

这样可控又有趣。

---

# 7. 现实任务要进入“确认门”

“发给导师”这种动作不能直接执行。

系统可以先在剧情里生成内容，但真正发送前必须确认：

```text
@DirectorBot:
我可以先生成 PPT 内容。至于“发给导师”，需要你确认导师是谁，以及是否真的发送。
[只生成内容] [生成并等待确认发送] [取消发送]
```

因为“发给导师”涉及现实世界操作，不能让剧情随便自动执行。

所以流程是：

```text
用户提出现实任务
-> 系统转成剧情内任务
-> 生成草稿
-> 用户确认
-> 才执行真实发送
```

---

# 8. 可以把这种插嘴叫做“剧情转轨”

我建议你设计一个专门模块：

```text
ReframeEngine
```

它处理用户突然大幅改方向的情况。

输入：

```json
{
  "current_world": "...",
  "user_interrupt": "我把向导变成电脑，让它搓一个环境调研 PPT 发给导师",
  "current_queue": "...",
  "world_constraints": {
    "genre": "magical_expedition",
    "elasticity": "medium",
    "allow_real_world_artifacts": true
  }
}
```

输出：

```json
{
  "decision": "accept_with_diegetic_adapter",
  "cancel_queue": true,
  "new_objective": "prepare_environment_research_presentation",
  "role_patches": "...",
  "speaker_queue": "...",
  "needs_user_confirmation": [
    "whether to generate actual PPT",
    "whether to send to mentor"
  ]
}
```

这里有个很重要的词：

## diegetic adapter

意思是：
把用户的现实请求翻译成世界内合理的形式。

比如：

```text
电脑 -> 奥术调研终端
PPT -> 学院汇报卷轴 / 研究简报 / 投影水晶
发给导师 -> 提交给野外课导师
```

这样既不打断世界观，又能满足用户的现实意图。

---

# 9. 你的例子可以有三种处理策略

用户说：

> 把向导变成电脑搓一个环境调研 PPT 发给导师。

## 策略一：完全接受，荒诞喜剧

```text
向导变电脑，开始生成 PPT。
```

适合轻松模式。

## 策略二：世界内转译，推荐

```text
向导触发“奥术终端形态”，可以整理资料并生成学院汇报。
```

适合魔法学院探险。

## 策略三：拆成游戏目标 + 现实产物

```text
游戏里：整理环境调研资料。
现实中：生成一个 PPT 草稿，等待用户确认是否发送。
```

最适合你的项目展示。

---

# 10. 后续 bot 的行为由“新任务图”控制

不只是改几句台词，还要改任务图。

旧任务图：

```text
追踪足迹
 -> 前往旧塔
 -> 遭遇月冠林蜥
 -> 完成观察记录
```

用户插嘴后变成：

```text
整理已有线索
 -> 补充环境数据
 -> 生成 PPT 大纲
 -> 让队伍成员分别贡献内容
 -> 用户确认是否继续探险或提交报告
```

不同 bot 的新职责：

| Bot | 新行为 |
|---|---|
| DirectorBot | 宣布剧情转轨，管理新目标 |
| GuideBot | 变成调研终端，负责整理材料 |
| ScholarBot | 提供生态和生物解释 |
| ScoutBot | 补充现场观察细节 |
| LogBot | 生成 PPT 结构和任务日志 |
| RuleBot | 判断这个变形是否有副作用 |
| EnvironmentBot | 提供天气、湿地、植被、光照数据 |

这样所有 bot 都知道自己该干什么。

---

# 11. 可以保留一点剧情后果

为了让用户的插嘴有游戏感，不要只是“好的，开始做 PPT”。

可以加入轻微后果：

```text
@RuleBot:
变形咒检定：4/6。成功，但艾洛-终端只能维持 10 分钟。

@CaptainBot:
“下次请提前通知队伍你要把人变成办公设备。”

@GuideBot:
“倒计时 10 分钟。建议先生成 PPT 大纲，再补图表。”
```

这会很好玩，也让世界仍然有规则。

---

# 12. 最终机制一句话

用户插嘴之后，后续 bot 不是“自由发挥跟上”，而是：

```text
Director 暂停当前剧情
-> 识别插嘴类型
-> 判断是否允许
-> 生成 Scenario Patch
-> 更新 WorldState / RoleCards / QuestGraph
-> 作废旧 SpeakerQueue
-> 生成新 SpeakerQueue
-> 后续 bot 只基于新状态发言
```

你这个例子最终会变成：

```text
魔法森林探险
  ↓ 用户插嘴
向导变成奥术调研终端
  ↓ 剧情转轨
当前目标变为“生成环境调研 PPT”
  ↓ 多 bot 重新分工
学者提供生态解释
斥候补现场观察
记录员整理结构
终端生成报告草稿
  ↓ 用户确认
继续探险 / 生成 PPT / 提交导师
```

这样既允许用户放飞，又不会让系统失控。