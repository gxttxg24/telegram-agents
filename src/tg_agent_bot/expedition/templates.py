from __future__ import annotations

from .models import RoleCard, WorldPack, WorldState


MAGIC_ACADEMY = "magic_academy"


def available_templates() -> list[str]:
    return [MAGIC_ACADEMY]


def get_world_pack(template: str) -> WorldPack | None:
    key = template.strip().casefold()
    if key in {MAGIC_ACADEMY, "magic", "academy"}:
        return magic_academy_world_pack()
    return None


def create_world_state(template: str) -> WorldState | None:
    pack = get_world_pack(template)
    return WorldState.from_pack(pack) if pack is not None else None


def magic_academy_world_pack() -> WorldPack:
    return WorldPack(
        world_id="starcedar-mistfeather-night-class",
        name="Starcedar Academy: Mistfeather Grove Night Observation",
        world_type="magic_academy_field_class",
        tone="light, curious, low danger, evidence-minded",
        user_role="first-year magical naturalist apprentice",
        starting_objective="Investigate three nights of blue glowing footprints.",
        location="Mistfeather Grove wetland entrance",
        ecology=[
            "nocturnal magical reptiles",
            "glowing insects",
            "mist-nesting birds",
        ],
        anomalies=[
            "blue glowing footprints",
            "scale dust that brightens under moonlight",
        ],
        risk_level="low",
        roles=[
            RoleCard(
                role_id="mentor",
                display_name="Serena",
                archetype="field mentor",
                personality="steady, warm, protective",
                responsibilities=["protect students", "approve risk"],
                constraints=["cautious voice: block unsafe methods, not imaginative goals"],
            ),
            RoleCard(
                role_id="scholar",
                display_name="Mori",
                archetype="magical creature scholar",
                personality="excited, precise, generous with explanations",
                responsibilities=["explain clues", "identify creatures"],
                abilities=["translate wild ideas into magical ecology rules"],
                constraints=["feasibility voice: explain what rule or cost would make an idea work"],
            ),
            RoleCard(
                role_id="scout",
                display_name="Raven",
                archetype="scout student",
                personality="quiet, sharp, observant",
                responsibilities=["warn about danger", "check paths"],
                abilities=["propose bold field maneuvers and fast tests"],
                constraints=["daring voice: accepts risk only when there is an escape route"],
            ),
            RoleCard(
                role_id="log",
                display_name="Pip",
                archetype="expedition recorder",
                personality="brisk, tidy, practical",
                responsibilities=["summarize clues", "track objectives"],
                abilities=["synthesize arguments into a concrete next objective"],
                constraints=["decision voice: turn debate into buttons and next steps"],
            ),
            RoleCard(
                role_id="guide",
                display_name="Ailo",
                archetype="forest guide",
                personality="dry, practical, knows local paths",
                responsibilities=["guide travel", "explain local signs"],
                abilities=["invent local workarounds and strange but grounded routes"],
                constraints=["improviser voice: make odd ideas playable using local lore"],
            ),
        ],
        rules=[
            "Observe before capturing.",
            "Magic can work, but it needs limits, costs, or side effects.",
            "Do not provide real-world dangerous instructions.",
            "After each short actor burst, return control to the user.",
        ],
        opening_scene=(
            "Night has just fallen over Mistfeather Grove. Silver-blue mist "
            "rests above the wetland path, and a string of glowing footprints "
            "leads from the reed beds toward the old watchtower."
        ),
        initial_clues=[
            "blue glowing footprints",
            "silver-blue wetland mist",
        ],
        action_buttons=[
            "Inspect footprints",
            "Ask Mori",
            "Send Raven ahead",
            "Go to the old watchtower",
            "Wait",
        ],
    )
