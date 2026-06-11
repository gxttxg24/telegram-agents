from __future__ import annotations

import asyncio
from typing import Any

from tg_agent_bot.expedition.generator import generate_world_state


class FakeLLM:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    async def json_reply(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_generate_world_state_builds_valid_pack_from_llm() -> None:
    llm = FakeLLM(
        {
            "name": "Cloud Library Survey",
            "world_type": "floating_archive_expedition",
            "tone": "bright, strange, lightly comic",
            "user_role": "visiting shelf-cartographer",
            "starting_objective": "Map why the cloud shelves are rearranging themselves.",
            "location": "the rain-index atrium",
            "ecology": ["paper moths", "index storms"],
            "anomalies": ["books shedding weather", "stairs changing tense"],
            "risk_level": "medium",
            "roles": [
                {
                    "role_id": "guide",
                    "display_name": "Quill",
                    "archetype": "archive guide",
                    "personality": "dry and mischievous",
                    "responsibilities": ["read local signs"],
                    "abilities": ["find hidden shelves"],
                    "constraints": ["makes weird ideas usable"],
                },
                {"role_id": "unknown", "display_name": "Should Be Ignored"},
            ],
            "rules": ["Every book has weather."],
            "opening_scene": "Rain falls upward between the shelves.",
            "opening_narration": ["A shelf coughs thunder, and the index cards scatter upward."],
            "opening_messages": [
                {
                    "role_id": "mentor",
                    "text": "The shelves are moving before anyone touches them.",
                },
                {
                    "role_id": "scholar",
                    "text": "That thunder came from the catalog, not the sky.",
                },
            ],
            "initial_clues": ["wet card catalog", "thunder in the indexes"],
            "action_buttons": ["Inspect wet catalog", "Ask Quill", "Climb tense stairs"],
        }
    )

    result = asyncio.run(generate_world_state(llm, "a floating library with weather books"))

    assert result.used_llm
    assert result.state.world_pack.name == "Cloud Library Survey"
    assert result.state.world_pack.risk_level == "medium"
    assert result.state.world_pack.role_by_id("guide").display_name == "Quill"
    assert result.state.world_pack.role_by_id("mentor") is not None
    assert result.state.world_pack.action_buttons[-1] == "Wait"
    assert result.state.world_pack.opening_narration == [
        "A shelf coughs thunder, and the index cards scatter upward."
    ]
    assert result.state.world_pack.opening_messages[0]["text"] == (
        "The shelves are moving before anyone touches them."
    )
    assert result.state.flags["world_generated_by_llm"] is True
    assert "mentor, scholar, scout, log, guide" in llm.calls[0]["system"]


def test_generate_world_state_falls_back_without_llm() -> None:
    result = asyncio.run(generate_world_state(None, "cozy mushroom train mystery"))

    assert not result.used_llm
    assert result.error == "llm_not_configured"
    assert "cozy mushroom train mystery" in result.state.world_pack.name
    assert result.state.world_pack.role_by_id("scout") is not None


def test_generate_world_state_uses_chinese_prompt_for_chinese_request() -> None:
    llm = FakeLLM(
        {
            "name": "月台蘑菇列车",
            "world_type": "cozy_train",
            "tone": "轻松、奇怪、适合调查",
            "user_role": "临时列车学徒",
            "starting_objective": "查明七号车厢为什么每站都会长出一扇新门。",
            "location": "灯菇月台",
            "ecology": ["票根甲虫"],
            "anomalies": ["会长门的车厢"],
            "risk_level": "low",
            "roles": [],
            "rules": [],
            "opening_scene": "列车吐出温暖的白雾，七号车厢多了一枚铜把手。",
            "initial_clues": ["新铜把手"],
            "action_buttons": ["检查铜把手"],
        }
    )

    result = asyncio.run(generate_world_state(llm, "我想玩一个蘑菇列车上的轻松调查"))

    assert result.used_llm
    assert result.state.flags["language"] == "zh"
    assert result.state.world_pack.action_buttons[-1] == "等待"
    assert result.state.world_pack.role_by_id("mentor").display_name == "瑟琳娜"
    assert "自然、完整的中文短句" in llm.calls[0]["user"]
    assert "Avoid translationese" in llm.calls[0]["system"]


def test_generate_world_state_chinese_fallback_is_fluent_chinese() -> None:
    result = asyncio.run(generate_world_state(None, "我想玩一个很怪的月亮菜市场"))

    assert result.state.flags["language"] == "zh"
    assert result.state.world_pack.name.startswith("生成远征：")
    assert result.state.world_pack.location == "新世界的入口"
    assert result.state.world_pack.action_buttons[-1] == "等待"
    assert result.state.world_pack.role_by_id("guide").display_name == "艾洛"


def test_generate_world_state_supplements_too_few_buttons() -> None:
    llm = FakeLLM(
        {
            "name": "Tiny Door Cave",
            "starting_objective": "Find why one tiny door keeps breathing.",
            "location": "the limestone threshold",
            "opening_scene": "A tiny red door breathes in the cave wall.",
            "initial_clues": ["breathing red door"],
            "action_buttons": ["Inspect red door"],
        }
    )

    result = asyncio.run(generate_world_state(llm, "tiny breathing door cave"))

    assert result.state.world_pack.action_buttons == [
        "Inspect red door",
        "Ask the scholar",
        "Send scout ahead",
        "Move deeper",
        "Wait",
    ]


def test_generate_world_state_falls_back_on_llm_error() -> None:
    result = asyncio.run(
        generate_world_state(FakeLLM(RuntimeError("bad json")), "moon market")
    )

    assert not result.used_llm
    assert result.error == "bad json"
    assert result.state.history[-1]["kind"] == "world_generation_fallback"
