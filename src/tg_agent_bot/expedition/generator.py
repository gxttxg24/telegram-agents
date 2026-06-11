from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .models import RoleCard, WorldPack, WorldState


logger = logging.getLogger(__name__)


class JSONWorldClient(Protocol):
    async def json_reply(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        ...


PUBLIC_ROLE_IDS = ("mentor", "scholar", "scout", "log", "guide")


ROLE_DEFAULTS = {
    "mentor": {
        "name": "Serena",
        "archetype": "field mentor",
        "personality": "steady, warm, protective",
        "responsibilities": ["protect the group", "name practical risks"],
        "abilities": ["turn unsafe plans into workable expedition steps"],
        "constraints": ["cautious voice: block unsafe methods, not imaginative goals"],
    },
    "scholar": {
        "name": "Mori",
        "archetype": "world scholar",
        "personality": "curious, precise, generous with explanations",
        "responsibilities": ["explain clues", "name world rules"],
        "abilities": ["translate wild ideas into world logic"],
        "constraints": ["feasibility voice: explain what cost or rule makes an idea work"],
    },
    "scout": {
        "name": "Raven",
        "archetype": "scout",
        "personality": "quiet, sharp, bold",
        "responsibilities": ["test paths", "spot danger"],
        "abilities": ["propose fast field tests and risky routes"],
        "constraints": ["daring voice: accepts risk only with an escape route"],
    },
    "log": {
        "name": "Pip",
        "archetype": "expedition recorder",
        "personality": "brisk, tidy, practical",
        "responsibilities": ["track objectives", "summarize evidence"],
        "abilities": ["synthesize debate into concrete next steps"],
        "constraints": ["decision voice: turn arguments into buttons"],
    },
    "guide": {
        "name": "Ailo",
        "archetype": "local guide",
        "personality": "dry, practical, improvisational",
        "responsibilities": ["explain local signs", "find grounded workarounds"],
        "abilities": ["make odd ideas playable using local lore"],
        "constraints": ["improviser voice: weird is welcome, but it needs a route"],
    },
}


ZH_ROLE_DEFAULTS = {
    "mentor": {
        "name": "瑟琳娜",
        "archetype": "带队导师",
        "personality": "稳重、温和、保护欲强",
        "responsibilities": ["保护队伍", "设定风险边界"],
        "abilities": ["把危险做法改写成可控的探索方案"],
        "constraints": ["保守派：阻止危险方法，但不否定想象目标"],
    },
    "scholar": {
        "name": "森理",
        "archetype": "世界规则学者",
        "personality": "好奇、严谨、乐于解释",
        "responsibilities": ["解释线索", "命名世界规则"],
        "abilities": ["把离奇想法翻译成世界内部逻辑"],
        "constraints": ["可行性派：说明一个想法需要什么代价或规则才成立"],
    },
    "scout": {
        "name": "鸦影",
        "archetype": "侦察员",
        "personality": "安静、敏锐、大胆",
        "responsibilities": ["试探道路", "发现危险"],
        "abilities": ["提出快速现场测试和冒险路线"],
        "constraints": ["激进派：只有存在退路时才接受风险"],
    },
    "log": {
        "name": "皮普",
        "archetype": "远征记录员",
        "personality": "利落、清楚、务实",
        "responsibilities": ["追踪目标", "整理证据"],
        "abilities": ["把争论整理成具体下一步"],
        "constraints": ["决策派：把讨论变成按钮和行动"],
    },
    "guide": {
        "name": "艾洛",
        "archetype": "本地向导",
        "personality": "嘴硬、务实、很会临场发挥",
        "responsibilities": ["解释本地迹象", "寻找接地气的替代路线"],
        "abilities": ["用本地传说把怪想法变得可玩"],
        "constraints": ["即兴派：怪可以，但必须有路可走"],
    },
}


@dataclass(frozen=True)
class WorldGenerationResult:
    state: WorldState
    used_llm: bool
    error: str = ""


async def generate_world_state(
    llm: JSONWorldClient | None,
    description: str,
) -> WorldGenerationResult:
    language = _language_for(description)
    if llm is None:
        state = WorldState.from_pack(_fallback_pack(description, language=language))
        state.flags["language"] = language
        return WorldGenerationResult(
            state=state,
            used_llm=False,
            error="llm_not_configured",
        )

    try:
        plan = await llm.json_reply(
            _system_prompt(language),
            _user_prompt(description, language),
            timeout_seconds=45.0,
        )
        pack = _pack_from_plan(plan, description, language=language)
        state = WorldState.from_pack(pack)
        state.flags["world_generated_by_llm"] = True
        state.flags["language"] = language
        state.record_event("world_generated", description, source="llm_generator")
        return WorldGenerationResult(state=state, used_llm=True)
    except Exception as exc:  # pragma: no cover - network/provider details vary
        logger.warning("LLM world generator failed; using fallback world: %s", exc)
        state = WorldState.from_pack(_fallback_pack(description, language=language))
        state.flags["world_generated_by_llm"] = False
        state.flags["language"] = language
        state.record_event("world_generation_fallback", str(exc), description=description)
        return WorldGenerationResult(state=state, used_llm=False, error=str(exc))


def _pack_from_plan(plan: dict[str, Any], description: str, *, language: str) -> WorldPack:
    if not isinstance(plan, dict):
        raise RuntimeError("World generator response must be a JSON object.")

    defaults = _text_defaults(language, description)
    name = _clean_text(plan.get("name"), max_chars=80) or defaults["name"]
    world_type = _clean_text(plan.get("world_type"), max_chars=60) or "generated_expedition"
    return WorldPack(
        world_id=_world_id(name),
        name=name,
        world_type=world_type,
        tone=_clean_text(plan.get("tone"), max_chars=120) or defaults["tone"],
        user_role=_clean_text(plan.get("user_role"), max_chars=120) or defaults["user_role"],
        starting_objective=(
            _clean_text(plan.get("starting_objective"), max_chars=180)
            or defaults["objective"]
        ),
        location=_clean_text(plan.get("location"), max_chars=100) or defaults["location"],
        ecology=_clean_list(plan.get("ecology"), max_items=5, max_chars=90),
        anomalies=_clean_list(plan.get("anomalies"), max_items=5, max_chars=90),
        risk_level=_risk_level(plan.get("risk_level")),
        roles=_roles_from_plan(plan.get("roles"), language=language),
        rules=_rules_from_plan(plan.get("rules"), language=language),
        opening_scene=(
            _clean_text(plan.get("opening_scene"), max_chars=700)
            or defaults["opening_scene"]
        ),
        initial_clues=_clean_list(plan.get("initial_clues"), max_items=5, max_chars=90)
        or [defaults["clue"]],
        action_buttons=_buttons_from_plan(plan.get("action_buttons"), language=language),
        opening_narration=_clean_list(
            plan.get("opening_narration"),
            max_items=2,
            max_chars=240,
        ) or [defaults["opening_narration"]],
        opening_messages=_opening_messages_from_plan(
            plan.get("opening_messages"),
            language=language,
        ),
    )


def _roles_from_plan(value: Any, *, language: str) -> list[RoleCard]:
    raw_roles = value if isinstance(value, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for item in raw_roles:
        if not isinstance(item, dict):
            continue
        role_id = _clean_text(item.get("role_id"), max_chars=40).casefold()
        if role_id in PUBLIC_ROLE_IDS:
            by_id[role_id] = item

    roles: list[RoleCard] = []
    for role_id in PUBLIC_ROLE_IDS:
        source = by_id.get(role_id, {})
        default = _role_defaults(language)[role_id]
        roles.append(
            RoleCard(
                role_id=role_id,
                display_name=_clean_text(source.get("display_name"), max_chars=40)
                or default["name"],
                archetype=_clean_text(source.get("archetype"), max_chars=80)
                or default["archetype"],
                personality=_clean_text(source.get("personality"), max_chars=140)
                or default["personality"],
                responsibilities=_clean_list(
                    source.get("responsibilities"),
                    max_items=4,
                    max_chars=80,
                )
                or list(default["responsibilities"]),
                abilities=_clean_list(source.get("abilities"), max_items=4, max_chars=80)
                or list(default["abilities"]),
                constraints=_clean_list(source.get("constraints"), max_items=4, max_chars=100)
                or list(default["constraints"]),
            )
        )
    return roles


def _rules_from_plan(value: Any, *, language: str) -> list[str]:
    rules = _clean_list(value, max_items=6, max_chars=120)
    if language == "zh":
        required = [
            "每轮角色短暂发言后，必须把控制权交还给用户。",
            "不要提供现实世界中的危险操作步骤。",
            "天马行空的想法应转化为可玩的世界后果和边界。",
        ]
    else:
        required = [
            "After each short actor burst, return control to the user.",
            "Do not provide real-world dangerous instructions.",
            "Wild ideas should be answered with playable world consequences and tradeoffs.",
        ]
    for rule in required:
        if rule not in rules:
            rules.append(rule)
    return rules[:6]


def _opening_messages_from_plan(value: Any, *, language: str) -> list[dict[str, str]]:
    raw_messages = value if isinstance(value, list) else []
    messages: list[dict[str, str]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role_id = _clean_text(item.get("role_id"), max_chars=40).casefold()
        if role_id not in PUBLIC_ROLE_IDS or role_id == "log":
            continue
        text = _clean_text(item.get("text"), max_chars=220)
        if not text:
            continue
        messages.append({"role_id": role_id, "text": text})
        if len(messages) >= 2:
            break
    if messages:
        return messages
    if language == "zh":
        return [
            {"role_id": "mentor", "text": "先别散开。这里有东西已经开始回应我们了。"},
            {"role_id": "scholar", "text": "我会看它接下来怎么变化；第二个证据通常来得很快。"},
        ]
    return [
        {"role_id": "mentor", "text": "Stay close. Something here has already started answering us."},
        {
            "role_id": "scholar",
            "text": "I will watch what changes next; the second piece of evidence usually arrives quickly.",
        },
    ]


def _buttons_from_plan(value: Any, *, language: str) -> list[str]:
    buttons = _clean_list(value, max_items=5, max_chars=32)
    fallback_buttons = (
        ["检查第一条线索", "询问学者", "派侦察员探路", "继续深入"]
        if language == "zh"
        else ["Inspect first clue", "Ask the scholar", "Send scout ahead", "Move deeper"]
    )
    for fallback in fallback_buttons:
        if len([button for button in buttons if not _is_wait_button(button)]) >= 4:
            break
        if _button_kind(fallback) in {_button_kind(button) for button in buttons}:
            continue
        if fallback not in buttons:
            buttons.append(fallback)
    if not any(button.casefold() in {"wait", "pause", "等待", "暂停"} for button in buttons):
        buttons.append("等待" if language == "zh" else "Wait")
    action_buttons = [button for button in buttons if not _is_wait_button(button)]
    wait_buttons = [button for button in buttons if _is_wait_button(button)]
    return (action_buttons[:4] + (wait_buttons[:1] or ["等待" if language == "zh" else "Wait"]))[:5]


def _is_wait_button(button: str) -> bool:
    return button.casefold() in {"wait", "pause", "等待", "暂停"}


def _button_kind(button: str) -> str:
    normalized = button.casefold()
    if any(term in normalized for term in ("inspect", "check", "observe", "检查", "观察")):
        return "observe"
    if any(term in normalized for term in ("ask", "询问", "问")):
        return "ask"
    if any(term in normalized for term in ("send", "scout", "派", "侦察")):
        return "scout"
    if any(term in normalized for term in ("move", "go", "enter", "deeper", "继续", "进入")):
        return "move"
    if _is_wait_button(button):
        return "wait"
    return normalized


def _fallback_pack(description: str, *, language: str) -> WorldPack:
    title_seed = _clean_text(description, max_chars=48) or (
        "生成的远征" if language == "zh" else "Generated Expedition"
    )
    defaults = _text_defaults(language, title_seed)
    return WorldPack(
        world_id=_world_id(title_seed),
        name=(
            f"生成远征：{title_seed}"
            if language == "zh"
            else f"Generated Expedition: {title_seed}"
        ),
        world_type="generated_fallback",
        tone=defaults["tone"],
        user_role=defaults["user_role"],
        starting_objective=defaults["objective"],
        location=defaults["location"],
        ecology=(
            ["尚未分类的本地生物", "会回应注意力的迹象"]
            if language == "zh"
            else ["unclassified local life", "signs that respond to attention"]
        ),
        anomalies=(
            ["这个世界会随着探索逐渐稳定"]
            if language == "zh"
            else ["the premise is unstable until explored"]
        ),
        risk_level="low",
        roles=[
            RoleCard(
                role_id=role_id,
                display_name=str(default["name"]),
                archetype=str(default["archetype"]),
                personality=str(default["personality"]),
                responsibilities=list(default["responsibilities"]),
                abilities=list(default["abilities"]),
                constraints=list(default["constraints"]),
            )
            for role_id, default in _role_defaults(language).items()
        ],
        rules=_rules_from_plan([], language=language),
        opening_scene=defaults["opening_scene"],
        initial_clues=(
            ["尚未稳定的设定", "第一处本地迹象"]
            if language == "zh"
            else ["unsettled premise", "first local sign"]
        ),
        action_buttons=_buttons_from_plan([], language=language),
        opening_narration=[defaults["opening_narration"]],
        opening_messages=_opening_messages_from_plan([], language=language),
    )


def _system_prompt(language: str) -> str:
    language_rule = (
        "Use natural, fluent Simplified Chinese for every visible text field. "
        "Avoid translationese, broken phrases, mixed English/Chinese, and awkward noun piles. "
        "Write short complete sentences that a Chinese Telegram group can read aloud naturally.\n"
        if language == "zh"
        else "Use natural, fluent English for every visible text field. Write short complete sentences.\n"
    )
    return (
        "You are a World Pack Generator for a Telegram-native multi-bot expedition runtime. "
        "Create an original, playable expedition world from the user's premise.\n"
        "Return JSON only.\n"
        f"{language_rule}"
        "Hard rules:\n"
        "- Generate exactly these public role_id values: mentor, scholar, scout, log, guide.\n"
        "- Give roles different stances: caution, feasibility, daring, synthesis, improvisation.\n"
        "- Keep the opening playable in a Telegram group: one concrete scene, clear objective, 3-5 clues, "
        "and at least 4 action buttons plus wait.\n"
        "- Do not include real-world dangerous instructions.\n"
        "- Buttons may have flavorful labels, but should imply observe, ask, assist, move, report, or wait.\n"
        "- Make every sentence locally coherent even if the premise is surreal.\n"
        "- Prefer concrete nouns and visible actions over abstract lore piles.\n"
        "- opening_scene must read like a scene already happening, not a premise summary. "
        "Mention visible motion, sound, weather, crowd behavior, or an object changing state.\n"
        "- opening_narration and opening_messages must be complete sentences written directly. "
        "Do not rely on the runtime to combine fields into sentences.\n"
        "JSON schema:\n"
        "{"
        '"name": string, "world_type": string, "tone": string, "user_role": string, '
        '"starting_objective": string, "location": string, "ecology": [string], '
        '"anomalies": [string], "risk_level": "low|medium|high", '
        '"roles": [{"role_id": string, "display_name": string, "archetype": string, '
        '"personality": string, "responsibilities": [string], "abilities": [string], '
        '"constraints": [string]}], '
        '"rules": [string], "opening_scene": string, "opening_narration": [string], '
        '"opening_messages": [{"role_id": string, "text": string}], "initial_clues": [string], '
        '"action_buttons": [string]'
        "}"
    )


def _user_prompt(description: str, language: str) -> str:
    return json.dumps(
        {
            "user_world_request": description,
            "output_language": "Simplified Chinese" if language == "zh" else "English",
            "fluency_requirement": (
                "所有可见文本必须是通顺、自然、完整的中文短句。不要中英夹杂，不要硬翻译。"
                if language == "zh"
                else "All visible text must be fluent natural English."
            ),
            "required_public_role_ids": list(PUBLIC_ROLE_IDS),
        },
        ensure_ascii=False,
        indent=2,
    )


def _clean_text(value: Any, *, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.strip().split())
    return cleaned[:max_chars]


def _clean_list(value: Any, *, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        cleaned = _clean_text(item, max_chars=max_chars)
        if cleaned and cleaned not in items:
            items.append(cleaned)
        if len(items) >= max_items:
            break
    return items


def _risk_level(value: Any) -> str:
    cleaned = _clean_text(value, max_chars=20).casefold()
    return cleaned if cleaned in {"low", "medium", "high"} else "low"


def _world_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return f"generated-{slug[:48] or 'expedition'}"


def _language_for(text: str) -> str:
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return "zh" if cjk_count >= 2 else "en"


def _role_defaults(language: str) -> dict[str, dict[str, object]]:
    return ZH_ROLE_DEFAULTS if language == "zh" else ROLE_DEFAULTS


def _text_defaults(language: str, description: str) -> dict[str, str]:
    title = _clean_text(description, max_chars=48)
    if language == "zh":
        return {
            "name": f"生成远征：{title or '未命名世界'}",
            "tone": "好奇、轻快、允许怪点子，但保持清楚边界",
            "user_role": "临时加入的探索者",
            "objective": f"调查这个设定背后的第一条规则：{title or '未知设定'}",
            "location": "新世界的入口",
            "opening_scene": (
                f"队伍停在新世界的入口。你的设定是：{title or '一个尚未命名的远征'}。"
                "周围的细节还在成形，但第一条线索已经出现。"
            ),
            "opening_narration": "空气突然安静下来，队伍意识到这个地方正在等待第一个决定。",
            "clue": "第一条本地迹象",
        }
    return {
        "name": f"Generated Expedition: {title or 'Unnamed World'}",
        "tone": "curious, improvisational, clear about consequences",
        "user_role": "guest explorer",
        "objective": f"Investigate the first rule behind this premise: {title or 'unknown premise'}",
        "location": "threshold of the new expedition",
        "opening_scene": (
            "The group gathers at the edge of a newly sketched world. "
            f"The user's premise hangs in the air: {title or 'an unnamed expedition'}. "
            "Details are still soft, but the first clue is already waiting."
        ),
        "opening_narration": (
            "The air goes quiet, and the group realizes the place is waiting for the first choice."
        ),
        "clue": "first local sign",
    }
