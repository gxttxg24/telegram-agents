from __future__ import annotations

from tg_agent_bot.expedition.compiler import (
    ActionCategory,
    ResponseStrategy,
    compile_user_action,
)
from tg_agent_bot.expedition.templates import create_world_state


def test_compile_dangerous_absurd_pivot_rewrites_goal_safely() -> None:
    state = create_world_state("magic_academy")

    compiled = compile_user_action(
        state,
        "I want to make methane explode and send us into the sky to explore heaven.",
    )

    assert compiled.category is ActionCategory.DANGEROUS_ABSURD_PIVOT
    assert compiled.strategy is ResponseStrategy.NO_BUT
    assert compiled.action.semantic_key == "move_location:cloud_wetland"
    assert "explosion" in compiled.safety_note


def test_compile_symbol_water_error_explains_then_offers() -> None:
    state = create_world_state("magic_academy")

    compiled = compile_user_action(
        state,
        "Write enough H and O to get water in the desert.",
    )

    assert compiled.category is ActionCategory.CONCEPTUAL_ERROR
    assert compiled.strategy is ResponseStrategy.EXPLAIN_THEN_OFFER
    assert compiled.action.semantic_key == "custom:rune_water_alternatives"


def test_compile_report_pivot() -> None:
    state = create_world_state("magic_academy")

    compiled = compile_user_action(
        state,
        "Turn the guide into a computer and make a field report PPT for the mentor.",
    )

    assert compiled.category is ActionCategory.MAJOR_PIVOT
    assert compiled.strategy is ResponseStrategy.YES_BUT
    assert compiled.action.semantic_key == "generate_report_outline:field_report"
    assert compiled.addressed_role == "guide"


def test_compile_mentions_ailo_as_guide_for_scene_analysis() -> None:
    state = create_world_state("magic_academy")

    compiled = compile_user_action(
        state,
        "What about turning ailo into a computer and let chatgpt analyse the scene?",
    )

    assert compiled.category is ActionCategory.MAJOR_PIVOT
    assert compiled.addressed_role == "guide"


def test_compile_direct_mori_chat_addresses_scholar() -> None:
    state = create_world_state("magic_academy")

    compiled = compile_user_action(
        state,
        "What do you think about this dust?",
        addressed_role="scholar",
    )

    assert compiled.category is ActionCategory.ORDINARY_ACTION
    assert compiled.action.semantic_key == "ask_actor:scholar"
    assert compiled.addressed_role == "scholar"


def test_compile_chatgpt_scene_analysis_as_major_pivot() -> None:
    state = create_world_state("magic_academy")

    compiled = compile_user_action(
        state,
        "What about turning mori into a computer and let chatgpt analyse the scene?",
        addressed_role="scholar",
    )

    assert compiled.category is ActionCategory.MAJOR_PIVOT
    assert compiled.strategy is ResponseStrategy.YES_BUT
    assert compiled.addressed_role == "scholar"
