from __future__ import annotations
import json
from typing import Type, TypeVar, Optional
from pydantic import BaseModel

from providers.text_base import TextProvider
from core.models import (
    Bible,
    CharacterSheet,
    VolumePlan,
    ChapterPlan,
    ChapterScript,
    PageScript,
    PanelScript,
    DialogueItem,
    PanelSizeType,
    BubbleType,
)

T = TypeVar("T", bound=BaseModel)


class MockTextProvider(TextProvider):
    """Offline mock text provider generating realistic manga story assets for development & testing."""

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        if "recap" in prompt.lower():
            return (
                "### Chapter Recap\n\n"
                "- Ren discovers the shattered cursed ink-stone beneath the temple floor.\n"
                "- The iron-masked pursuers breach the outer sanctuary, demanding the scroll.\n"
                "- Ren unleashes the nascent ink blade, repelling the vanguard but shattering his arm brace.\n"
                "- **Cliffhanger:** The masked commander reveals the mark of the Crimson Shogunate on his neck."
            )
        return "Manga story beat generated offline by MockTextProvider."

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> T:
        if response_model == Bible:
            sample_bible = Bible(
                logline="A disgraced apprentice calligrapher discovers forbidden living ink that can carve reality, hunted across neo-feudal Kyoto by an iron-masked shogunate.",
                synopsis="In a steam-punk neo-Edo Japan, calligraphy and ink mastery govern ancient spirit seals. When apprentice Ren accidentally binds his blood to an ancient Black Dragon ink stone, he is pursued by the Kurogane Clan while seeking to clear his master's murdered name.",
                world_rules=[
                    "Living Ink requires spiritual focus; exceeding mental stamina causes ink-rot on the wielder's flesh.",
                    "The Crimson Shogunate controls all official ink quarries; unregistered scribes are branded outlaws.",
                    "Summoned ink constructs dissolve upon contact with salt water or consecrated iron."
                ],
                themes=["Redemption", "Artistic Passion vs Destruction", "Freedom under Oppression"],
                characters=[
                    CharacterSheet(
                        name="Ren Kuroba",
                        role="Protagonist",
                        visual_descriptor="17-year-old youth with messy raven spiky hair, worn black haori jacket with rolled sleeves revealing bandage-wrapped forearms, intense amber eyes, ink-stained fingertips, carrying a heavy brass brush sheath across his back",
                        personality="Stubborn, deeply protective of innocents, prone to reckless improvisation in combat, artistic perfectionist",
                        motivation_arc="Uncover who framed his master for treason and master the unruly living dragon ink before it consumes his life",
                        reference_images=[]
                    ),
                    CharacterSheet(
                        name="Aoi Suzumori",
                        role="Ally / Tactician",
                        visual_descriptor="18-year-old shrine maiden engineer, sharp indigo bob haircut with brass hairpin goggles, white and vermilion miko combat vest, twin tanto daggers at waist, pragmatic guarded expression",
                        personality="Analytical, blunt, quick-witted, secretly harboring guilt over her family's weapons workshop",
                        motivation_arc="Atones for her clan's mass-produced spirit weapons by sabotaging the Shogunate from within",
                        reference_images=[]
                    ),
                    CharacterSheet(
                        name="Commander Kazuma",
                        role="Antagonist",
                        visual_descriptor="Tall imposing warrior, full lacquered crimson samurai armor with oni half-mask, scarred left jaw, silver ponytail, wields a dual-edged odachi capable of severing spirit energy",
                        personality="Cold, unyielding adherence to order, merciless executioner of rogue scribes",
                        motivation_arc="Enforces the Shogun's absolute dominion at any moral cost",
                        reference_images=[]
                    )
                ],
                visual_style_guide="High-contrast Japanese ink wash manga, sharp angular linework, heavy solid black shadows, dramatic cross-hatching, explosive motion speedlines.",
                is_approved=False,
            )
            return sample_bible  # type: ignore

        elif response_model == VolumePlan:
            sample_volume = VolumePlan(
                volume_number=1,
                volume_title="Volume 1: The Dragon's Inception",
                volume_logline="From humble forge to bloodied exile: Ren awakens the forbidden ink, flees Kyoto, and rallies his first ally.",
                pacing_outline="Act 1 (Ch 1-2): Inciting incident and escape. Act 2 (Ch 3-4): Pursuit across the misty Bamboo Ridge and clash at the iron bridge. Act 3 (Ch 5): Climax against Commander Kazuma and descent into the underground.",
                chapters=[
                    ChapterPlan(
                        chapter_number=1,
                        title="Blood on Parchment",
                        target_pages=16,
                        story_arc_goal="Introduce Ren's calligraphy mastery, the murder of Master Gen, and awakening the living ink.",
                        conflict="Shogunate assassins storm the sanctuary; Ren is trapped in the archive.",
                        climax_cliffhanger="Ren slices through the temple wall with an ink blade, leaping into the midnight rain."
                    ),
                    ChapterPlan(
                        chapter_number=2,
                        title="Shadows of the Bamboo Ridge",
                        target_pages=16,
                        story_arc_goal="Ren escapes into the wilderness, meets runaway engineer Aoi.",
                        conflict="Aoi mistakes Ren for a bounty hunter; mechanical spirit hounds track them.",
                        climax_cliffhanger="A massive brass automaton corners both of them over a misty ravine."
                    ),
                    ChapterPlan(
                        chapter_number=3,
                        title="The Resonance of Ink",
                        target_pages=16,
                        story_arc_goal="Ren and Aoi combine ink and clockwork to defeat the mechanical stalkers.",
                        conflict="Ren's ink-rot spreads up his wrist as his stamina depletes.",
                        climax_cliffhanger="Aoi reveals she knows Master Gen's secret journal cipher."
                    ),
                    ChapterPlan(
                        chapter_number=4,
                        title="The Burning Gate",
                        target_pages=16,
                        story_arc_goal="Infiltration of the Shogunate checkpoint at the Iron Gorge.",
                        conflict="Commander Kazuma's vanguard blocks the pass with cannon artillery.",
                        climax_cliffhanger="Commander Kazuma draws his spirit-severing odachi directly in Ren's path."
                    ),
                    ChapterPlan(
                        chapter_number=5,
                        title="Severed Bonds",
                        target_pages=18,
                        story_arc_goal="Volume climax duel between Ren and Kazuma, triggering Ren's full dragon awakening.",
                        conflict="Kazuma shatters Ren's brass brush; ink spirals uncontrollably.",
                        climax_cliffhanger="Ren unleashes a colossal ink dragon that levels the gorge, falling unconscious into the river."
                    ),
                ],
                is_approved=False,
            )
            return sample_volume  # type: ignore

        elif response_model == ChapterScript:
            # Parse chapter number if present in prompt or default to 1
            ch_num = 1
            for word in prompt.split():
                if word.isdigit():
                    ch_num = int(word)
                    break

            sample_script = ChapterScript(
                chapter_number=ch_num,
                title=f"Blood on Parchment - Act {ch_num}",
                summary=f"Chapter {ch_num} establishes the stakes as Ren discovers his mentor's sanctuary breached and unleashes the living dragon ink.",
                pages=[
                    PageScript(
                        page_number=1,
                        page_notes="Hook page: Establish the tranquil temple atmosphere before sudden devastation.",
                        panels=[
                            PanelScript(
                                panel_number=1,
                                panel_size=PanelSizeType.WIDE,
                                camera_angle="Wide Establishing Shot",
                                description="Moonlit courtyard of Master Gen's mountain sanctuary. Cherry blossom petals drift across stone lanterns. Silence hangs heavy in the midnight mist.",
                                characters_present=[],
                                dialogue=[
                                    DialogueItem(speaker="Narrator", text="Kyoto, Year 17 of the Iron Reign. Some arts were meant to stay buried.", type=BubbleType.NARRATOR)
                                ],
                                pacing_notes="Quiet, calm before the storm"
                            ),
                            PanelScript(
                                panel_number=2,
                                panel_size=PanelSizeType.SMALL,
                                camera_angle="Close-up",
                                description="Ren Kuroba's hand holding a heavy horsehair calligraphy brush suspended a millimeter above pure white parchment. An ink drop trembles at the brush tip.",
                                characters_present=["Ren Kuroba"],
                                dialogue=[
                                    DialogueItem(speaker="SFX", text="PATA...", type=BubbleType.SFX, sfx_intensity="Low")
                                ],
                                pacing_notes="Heightened sensory focus"
                            ),
                            PanelScript(
                                panel_number=3,
                                panel_size=PanelSizeType.WIDE,
                                camera_angle="Dutch Angle Medium Shot",
                                description="The sliding shoji door suddenly violently explodes into splinters. Black-clad armored vanguard troops breach the threshold with gleaming naginatas.",
                                characters_present=["Ren Kuroba"],
                                dialogue=[
                                    DialogueItem(speaker="SFX", text="BASHAAAN!!", type=BubbleType.SFX, sfx_intensity="Extreme"),
                                    DialogueItem(speaker="Ren Kuroba", text="Master Gen?!", type=BubbleType.SHOUT, tail_position="bottom-left")
                                ],
                                pacing_notes="Jolt of explosive action"
                            )
                        ]
                    ),
                    PageScript(
                        page_number=2,
                        page_notes="Escalation: Reveal of the cursed ink-stone and the threat.",
                        panels=[
                            PanelScript(
                                panel_number=1,
                                panel_size=PanelSizeType.TALL,
                                camera_angle="Low Angle Shot",
                                description="An imposing Shogunate officer stands in the doorway holding a sealed writ, crimson ribbons fluttering in the draft. His cold eyes lock onto Ren.",
                                characters_present=["Ren Kuroba"],
                                dialogue=[
                                    DialogueItem(speaker="Officer", text="Hand over the Black Dragon stone, boy. The traitor Gen has already answered for his sins.", type=BubbleType.SPEECH, tail_position="top-right")
                                ],
                                pacing_notes="Chilling dread"
                            ),
                            PanelScript(
                                panel_number=2,
                                panel_size=PanelSizeType.SMALL,
                                camera_angle="Extreme Close-up",
                                description="Ren's amber eyes widen with fury and grief. Blood drips from his cut palm onto the ancient ink stone on the desk.",
                                characters_present=["Ren Kuroba"],
                                dialogue=[
                                    DialogueItem(speaker="Ren Kuroba", text="(You... you killed him...)", type=BubbleType.THOUGHT),
                                    DialogueItem(speaker="SFX", text="DOKI DOKI...", type=BubbleType.SFX, sfx_intensity="Medium")
                                ],
                                pacing_notes="Internal boiling rage"
                            ),
                            PanelScript(
                                panel_number=3,
                                panel_size=PanelSizeType.SPLASH,
                                camera_angle="Dynamic Low Angle Impact Shot",
                                description="The ink on the desk erupts into serpentine black tendrils with glowing gold eyes, coiling around Ren's forearm and forming a razor-sharp crescent blade of solid black liquid.",
                                characters_present=["Ren Kuroba"],
                                dialogue=[
                                    DialogueItem(speaker="SFX", text="ZAZAZAAAA--!!", type=BubbleType.SFX, sfx_intensity="Extreme"),
                                    DialogueItem(speaker="Ren Kuroba", text="DON'T TOUCH MY MASTER'S WORK!", type=BubbleType.SHOUT, tail_position="center")
                                ],
                                pacing_notes="Page-turn climax moment"
                            )
                        ]
                    ),
                    PageScript(
                        page_number=3,
                        page_notes="Climax of the encounter and the daring escape.",
                        panels=[
                            PanelScript(
                                panel_number=1,
                                panel_size=PanelSizeType.WIDE,
                                camera_angle="Cinematic Horizontal Pan",
                                description="Ren swings the ink blade in a wide arc. A wave of pitch-black crescent energy cleaves clean through the temple wall and knocks back the vanguard soldiers in a blast of pressurized air.",
                                characters_present=["Ren Kuroba"],
                                dialogue=[
                                    DialogueItem(speaker="SFX", text="DOGOOOON!!", type=BubbleType.SFX, sfx_intensity="Extreme")
                                ],
                                pacing_notes="Overwhelming explosive power"
                            ),
                            PanelScript(
                                panel_number=2,
                                panel_size=PanelSizeType.TALL,
                                camera_angle="Bird's Eye / High Angle",
                                description="Ren vaults through the cleaved timber opening into the stormy night sky, clutching the ink stone to his chest as rain pelts his face. Below, the lanterns of the Shogunate search party ignite across the valley.",
                                characters_present=["Ren Kuroba"],
                                dialogue=[
                                    DialogueItem(speaker="Ren Kuroba", text="(I swear... I will finish what you started, Master.)", type=BubbleType.THOUGHT),
                                    DialogueItem(speaker="Narrator", text="The hunt begins.", type=BubbleType.NARRATOR)
                                ],
                                pacing_notes="Heroic escape into the unknown"
                            )
                        ]
                    )
                ],
                is_approved=False
            )
            return sample_script  # type: ignore

        # Fallback empty model initialization
        return response_model()

