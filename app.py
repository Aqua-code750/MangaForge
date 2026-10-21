from __future__ import annotations
import os
import json
import time
import random
from pathlib import Path
from typing import Optional, Dict

import streamlit as st
from dotenv import load_dotenv

from core.models import (
    ProjectSettings,
    ProjectMode,
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
from core.storage import StorageManager, slugify
from core.pipeline import (
    generate_bible,
    generate_volume_plan,
    generate_chapter_script,
    generate_chapter_recap,
    build_panel_image_prompt,
    build_lettering_data_for_chapter,
    load_system_prompt,
)
from core.image_engine import (
    generate_panel_image,
    batch_generate_chapter_panels,
    estimate_generation_cost,
    get_panel_dimensions,
)
from core.page_composer import (
    compose_single_page,
    compose_and_save_page,
)
from core.print_exporter import export_print_volume
from core.webtoon_exporter import export_webtoon_chapter
from core.layout_engine import (
    calculate_canvas_geometry,
    Rect,
)
from providers.text_anthropic import AnthropicTextProvider
from providers.text_gemini import GeminiTextProvider
from providers.text_mock import MockTextProvider
from providers.image_base import ImageProvider, compute_image_cache_key
from providers.image_mock import MockImageProvider
from providers.image_custom import CustomImageProvider

load_dotenv()

# ==============================================================================
# STREAMLIT CONFIG & MOBILE-RESPONSIVE CSS
# ==============================================================================
st.set_page_config(
    page_title="MangaForge - Manga Studio",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom responsive CSS for phone and desktop screens
st.markdown(
    """
    <style>
    /* Mobile-first and high-contrast Manga aesthetics */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Responsive container adjustments */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        button {
            width: 100% !important;
            min-height: 44px !important; /* Touch target size */
            margin-bottom: 0.4rem !important;
        }
        .manga-header h1 {
            font-size: 1.6rem !important;
        }
    }

    /* Badge & Card stylings */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    .badge-approved {
        background-color: #10b981;
        color: white;
    }
    .badge-draft {
        background-color: #f59e0b;
        color: white;
    }
    .badge-pending {
        background-color: #6b7280;
        color: white;
    }

    .manga-card {
        border: 2px solid #e5e7eb;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: rgba(255, 255, 255, 0.03);
    }
    .character-card {
        border-left: 4px solid #3b82f6;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
        background-color: rgba(59, 130, 246, 0.05);
        border-radius: 0 8px 8px 0;
    }
    .panel-card {
        border: 1px solid #4b5563;
        border-radius: 8px;
        padding: 0.75rem;
        margin-top: 0.5rem;
        margin-bottom: 0.75rem;
        background-color: rgba(0, 0, 0, 0.1);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

storage = StorageManager()

# ==============================================================================
# SIDEBAR: PROJECT PICKER, PROVIDER & SETTINGS
# ==============================================================================
with st.sidebar:
    st.title("⚡ MangaForge")
    st.caption("One original manga volume at a time.")
    st.divider()

    # --- Project Selection ---
    existing_projects = storage.list_projects()
    project_options = ["+ Create New Manga Project"] + existing_projects

    # Store selected project in session_state
    if "current_slug" not in st.session_state:
        st.session_state.current_slug = existing_projects[0] if existing_projects else "+ Create New Manga Project"

    selected_project = st.selectbox(
        "Current Manga Project",
        options=project_options,
        index=project_options.index(st.session_state.current_slug) if st.session_state.current_slug in project_options else 0,
    )
    st.session_state.current_slug = selected_project

    # --- Create Project Form ---
    if selected_project == "+ Create New Manga Project":
        st.subheader("New Project")
        with st.form("create_project_form"):
            new_title = st.text_input("Manga Title", value="Shadows of Kyoto")
            new_genre = st.selectbox("Genre / Demographic", ["Dark Fantasy Shonen", "Cyberpunk Seinen", "Supernatural Horror", "Action Shonen", "Sci-Fi Mystery", "Slice of Life"])
            new_rating = st.selectbox("Content Rating", ["Teen (13+)", "All Ages", "Mature (18+)"])
            new_mode = st.selectbox("Target Format", [ProjectMode.BOTH.value, ProjectMode.PRINT.value, ProjectMode.WEBTOON.value])
            new_ch_count = st.number_input("Chapters per Volume", min_value=1, max_value=20, value=5)
            new_style = st.text_area(
                "Locked Art Style",
                value="High-contrast Japanese ink line art, heavy shadows, crisp screentones, dynamic manga paneling",
                height=70,
            )
            create_submitted = st.form_submit_button("Create Project", use_container_width=True)

            if create_submitted and new_title.strip():
                slug = slugify(new_title)
                settings = ProjectSettings(
                    title=new_title.strip(),
                    slug=slug,
                    genre=new_genre,
                    rating=new_rating,
                    mode=ProjectMode(new_mode),
                    style_traits=new_style.strip(),
                    chapters_per_volume=int(new_ch_count),
                )
                storage.init_project_structure(settings)
                st.session_state.current_slug = slug
                st.success(f"Project '{new_title}' created!")
                st.rerun()

    # --- Provider Settings ---
    st.divider()
    st.subheader("🤖 Text AI Provider")
    gemini_key_default = os.getenv("GEMINI_API_KEY", os.getenv("IMAGE_API_KEY", ""))
    anthropic_key_default = os.getenv("ANTHROPIC_API_KEY", "")

    provider_options = ["Anthropic Claude", "Google Gemini", "Mock Provider (Offline)"]
    if anthropic_key_default:
        default_idx = 0
    elif gemini_key_default:
        default_idx = 1
    else:
        default_idx = 2

    provider_choice = st.radio(
        "Model Engine",
        provider_options,
        index=default_idx,
    )

    if provider_choice == "Anthropic Claude":
        sidebar_key = st.text_input(
            "Anthropic API Key",
            value=anthropic_key_default,
            type="password",
            help="Set in .env or enter here for the session",
        )
        model_name = st.selectbox(
            "Claude Model",
            ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            index=0,
        )
        if sidebar_key:
            provider = AnthropicTextProvider(api_key=sidebar_key, model=model_name)
        else:
            st.warning("⚠️ No Anthropic key found. Switched to Mock Provider.")
            provider = MockTextProvider()
    elif provider_choice == "Google Gemini":
        sidebar_gemini_key = st.text_input(
            "Gemini API Key",
            value=gemini_key_default,
            type="password",
            help="Set in .env or enter here for the session",
        )
        gemini_model_name = st.selectbox(
            "Gemini Model",
            ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash", "gemini-pro-latest", "gemini-2.5-flash"],
            index=0,
            help="gemini-3.8-flash is the active high-speed multimodal model on Google AI Studio.",
        )
        if sidebar_gemini_key:
            provider = GeminiTextProvider(api_key=sidebar_gemini_key, model=gemini_model_name)
        else:
            st.warning("⚠️ No Gemini key found. Switched to Mock Provider.")
            provider = MockTextProvider()
    else:
        st.info("💡 Running offline with Mock Text Provider.")
        provider = MockTextProvider()

    # --- Image Provider Settings ---
    st.divider()
    st.subheader("🎨 Image AI Provider")
    image_key_default = os.getenv("IMAGE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    img_choice = st.radio(
        "Image Engine",
        ["Mock Provider (Offline)", "Google Generative AI / Custom"],
        index=0 if not image_key_default else 1,
        help="Use Mock for instant offline testing, or Google Generative AI for panel generation."
    )
    if img_choice == "Google Generative AI / Custom":
        custom_key = st.text_input(
            "Google API Key (IMAGE_API_KEY / GEMINI_API_KEY)",
            value=image_key_default,
            type="password",
            help="Set in .env or enter here"
        )
        img_model_name = st.selectbox(
            "Image Generation Model",
            [
                "nano-banana-pro-preview",
                "gemini-nano-banana-2.1",
                "gemini-2.5-flash-image",
                "gemini-3.1-flash-image",
                "imagen-3.0-generate-002",
            ],
            index=0,
            help="Google AI Studio image model (e.g. Nano Banana Pro Preview or Gemini Image)"
        )
        image_provider = CustomImageProvider(api_key=custom_key, model_name=img_model_name)
        st.caption("ℹ️ Powered by `providers/image_custom.py` via `google-generativeai`.")
    else:
        st.info("💡 Mock Image Provider renders instant offline panel placeholders.")
        image_provider = MockImageProvider()

# ==============================================================================
# MAIN WORKSPACE
# ==============================================================================
slug = st.session_state.get("current_slug", "+ Create New Manga Project")
settings = storage.load_settings(slug) if (slug and slug != "+ Create New Manga Project") else None

if not settings:
    st.info("👈 Please select an existing manga project or create a new one in the sidebar to begin.")
    st.stop()

# Load current project artifacts
bible = storage.load_bible(slug)
volume_plan = storage.load_volume_plan(slug)

# Header & Overview
st.markdown(f"## 📖 {settings.title}")

# Calculate Volume Progress Statistics
bible_status = "Approved" if (bible and bible.is_approved) else ("Draft" if bible else "Pending")
bible_color = "badge-approved" if bible_status == "Approved" else ("badge-draft" if bible_status == "Draft" else "badge-pending")

plan_status = "Approved" if (volume_plan and volume_plan.is_approved) else ("Draft" if volume_plan else "Pending")
plan_color = "badge-approved" if plan_status == "Approved" else ("badge-draft" if plan_status == "Draft" else "badge-pending")

scripted_chapters = 0
approved_chapters = 0
total_panels_in_vol = 0
generated_panels_in_vol = 0

for ch_idx in range(1, settings.chapters_per_volume + 1):
    ch_s = storage.load_chapter_script(slug, ch_idx)
    if ch_s:
        scripted_chapters += 1
        if ch_s.is_approved:
            approved_chapters += 1
        ch_manifest = storage.load_panels_manifest(slug, ch_idx)
        for page in ch_s.pages:
            for pnl in page.panels:
                total_panels_in_vol += 1
                pid = f"p{page.page_number}_panel{pnl.panel_number}"
                if pid in ch_manifest.panels and storage.get_panel_image_path(slug, ch_idx, pid).exists():
                    generated_panels_in_vol += 1

col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
with col_stat1:
    st.markdown(f"**Bible:** <span class='status-badge {bible_color}'>{bible_status}</span>", unsafe_allow_html=True)
with col_stat2:
    st.markdown(f"**Volume Plan:** <span class='status-badge {plan_color}'>{plan_status}</span>", unsafe_allow_html=True)
with col_stat3:
    st.markdown(f"**Chapters:** `{approved_chapters}/{settings.chapters_per_volume} Approved`")
with col_stat4:
    st.markdown(f"**Art Panels:** `{generated_panels_in_vol}/{total_panels_in_vol} Rendered`")

st.caption(f"**Genre:** {settings.genre} | **Rating:** {settings.rating} | **Mode:** {settings.mode.value} | **Trim:** {settings.trim_size} | **Reading:** {settings.reading_direction}")

# Stage Navigation Tabs
tabs = st.tabs([
    "1. Story Bible",
    "2. Volume Plan",
    "3. Chapter Script",
    "4. Art & Panels",
    "5. Lettering & Layout",
    "6. Export Studio",
])

# ==============================================================================
# TAB 1: STORY BIBLE
# ==============================================================================
with tabs[0]:
    st.subheader("📚 Stage 1: Story Bible & Character Sheets")
    st.markdown(
        "The Story Bible defines the foundation: logline, world rules, and character sheets "
        "with **locked visual descriptors** injected into panel generation."
    )

    if bible:
        badge_cls = "badge-approved" if bible.is_approved else "badge-draft"
        badge_txt = "Approved & Locked" if bible.is_approved else "Draft (Awaiting Approval)"
        st.markdown(f'<span class="status-badge {badge_cls}">{badge_txt}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge badge-pending">Not Generated</span>', unsafe_allow_html=True)

    # Generation Form
    with st.expander("✨ Generate / Re-generate Bible", expanded=(bible is None)):
        user_pitch = st.text_area(
            "Manga Premise, Lore, and Key Ideas",
            value="A young calligraphy apprentice discovers that his ink can animate ancient spirits. When his master is assassinated by the Shogun's secret police, he must flee across neo-feudal Kyoto.",
            height=100,
        )
        if st.button("Generate Bible with AI", type="primary", use_container_width=True):
            with st.spinner("Mangaka Story Brain is crafting the Story Bible..."):
                try:
                    new_bible = generate_bible(settings, user_pitch, provider)
                    storage.save_bible(slug, new_bible)
                    st.success("Story Bible generated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating Bible: {e}")

    # Editable Bible View
    if bible:
        with st.form("bible_edit_form"):
            st.markdown("### Core Narrative")
            edited_logline = st.text_input("Logline", value=bible.logline)
            edited_synopsis = st.text_area("Narrative Synopsis", value=bible.synopsis, height=120)
            edited_style = st.text_area("Visual Style Guide", value=bible.visual_style_guide, height=70)

            st.markdown("### World Rules (one per line)")
            rules_str = "\n".join(bible.world_rules)
            edited_rules_str = st.text_area("World Rules", value=rules_str, height=100)

            st.markdown("### Character Sheets")
            edited_characters = []
            for idx, c in enumerate(bible.characters):
                st.markdown(f"**Character {idx+1}: {c.name} ({c.role})**")
                col_c1, col_c2 = st.columns([1, 1])
                with col_c1:
                    c_name = st.text_input("Name", value=c.name, key=f"c_name_{idx}")
                    c_role = st.text_input("Role", value=c.role, key=f"c_role_{idx}")
                    c_personality = st.text_area("Personality", value=c.personality, key=f"c_pers_{idx}", height=65)
                with col_c2:
                    c_desc = st.text_area(
                        "Locked Visual Descriptor (Prompt Injection)",
                        value=c.visual_descriptor,
                        key=f"c_desc_{idx}",
                        height=95,
                        help="Exact clothing, hair, scars, silhouettes used for image consistency."
                    )
                    c_arc = st.text_input("Motivation Arc", value=c.motivation_arc, key=f"c_arc_{idx}")

                edited_characters.append(
                    CharacterSheet(
                        name=c_name,
                        role=c_role,
                        visual_descriptor=c_desc,
                        personality=c_personality,
                        motivation_arc=c_arc,
                        reference_images=c.reference_images,
                    )
                )
                st.divider()

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                save_bible_btn = st.form_submit_button("💾 Save Edits", use_container_width=True)
            with col_btn2:
                approve_bible_btn = st.form_submit_button("✅ Approve Bible", type="primary", use_container_width=True)

            if save_bible_btn:
                bible.logline = edited_logline
                bible.synopsis = edited_synopsis
                bible.visual_style_guide = edited_style
                bible.world_rules = [r.strip() for r in edited_rules_str.split("\n") if r.strip()]
                bible.characters = edited_characters
                storage.save_bible(slug, bible)
                st.success("Story Bible updated!")
                st.rerun()

            if approve_bible_btn:
                bible.logline = edited_logline
                bible.synopsis = edited_synopsis
                bible.visual_style_guide = edited_style
                bible.world_rules = [r.strip() for r in edited_rules_str.split("\n") if r.strip()]
                bible.characters = edited_characters
                bible.is_approved = True
                storage.save_bible(slug, bible)
                st.success("Story Bible approved! You can now proceed to Stage 2: Volume Plan.")
                st.rerun()


# ==============================================================================
# TAB 2: VOLUME PLAN
# ==============================================================================
with tabs[1]:
    st.subheader("🗺️ Stage 2: Volume Plan & Chapter Breakdown")
    st.markdown(
        f"Defines the complete narrative pacing structure for **Volume 1** across all **{settings.chapters_per_volume} chapters**."
    )

    if not bible:
        st.warning("⚠️ Please generate the Story Bible in Stage 1 first.")
    elif not bible.is_approved:
        st.info("ℹ️ Story Bible is currently in Draft. You can still generate the Volume Plan, but approving the Bible first is recommended.")

    if volume_plan:
        badge_cls = "badge-approved" if volume_plan.is_approved else "badge-draft"
        badge_txt = "Approved & Locked" if volume_plan.is_approved else "Draft (Awaiting Approval)"
        st.markdown(f'<span class="status-badge {badge_cls}">{badge_txt}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge badge-pending">Not Generated</span>', unsafe_allow_html=True)

    if bible:
        with st.expander("✨ Generate / Re-generate Volume Plan", expanded=(volume_plan is None)):
            plan_notes = st.text_area(
                "Creator Pacing Notes",
                value="Build a classic 3-act escalation: Ch 1 escape, Ch 2-3 rising encounter and companion team-up, Ch 4 checkpoint ambush, Ch 5 climactic showdown.",
                height=80,
            )
            if st.button("Generate Volume Plan with AI", type="primary", use_container_width=True):
                with st.spinner("Structuring volume pacing and chapter arcs..."):
                    try:
                        new_plan = generate_volume_plan(settings, bible, provider, plan_notes)
                        storage.save_volume_plan(slug, new_plan)
                        st.success("Volume Plan generated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generating Volume Plan: {e}")

    if volume_plan:
        with st.form("volume_plan_edit_form"):
            st.markdown("### Volume Overview")
            v_title = st.text_input("Volume Title", value=volume_plan.volume_title)
            v_logline = st.text_area("Volume Arc Logline", value=volume_plan.volume_logline, height=70)
            v_pacing = st.text_area("Pacing Outline", value=volume_plan.pacing_outline, height=80)

            st.markdown("### Chapter Breakdown")
            edited_chapters = []
            for ch in volume_plan.chapters:
                st.markdown(f"#### Chapter {ch.chapter_number}: {ch.title}")
                col_p1, col_p2 = st.columns([1, 1])
                with col_p1:
                    c_title = st.text_input("Title", value=ch.title, key=f"ch_title_{ch.chapter_number}")
                    c_pages = st.number_input("Target Pages", min_value=4, max_value=40, value=ch.target_pages, key=f"ch_pages_{ch.chapter_number}")
                    c_goal = st.text_area("Story Arc Goal", value=ch.story_arc_goal, key=f"ch_goal_{ch.chapter_number}", height=65)
                with col_p2:
                    c_conflict = st.text_area("Central Conflict", value=ch.conflict, key=f"ch_conf_{ch.chapter_number}", height=65)
                    c_climax = st.text_area("Cliffhanger / Climax", value=ch.climax_cliffhanger, key=f"ch_climax_{ch.chapter_number}", height=65)

                edited_chapters.append(
                    ChapterPlan(
                        chapter_number=ch.chapter_number,
                        title=c_title,
                        target_pages=int(c_pages),
                        story_arc_goal=c_goal,
                        conflict=c_conflict,
                        climax_cliffhanger=c_climax,
                    )
                )
                st.divider()

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                save_plan_btn = st.form_submit_button("💾 Save Volume Plan", use_container_width=True)
            with col_btn2:
                approve_plan_btn = st.form_submit_button("✅ Approve Volume Plan", type="primary", use_container_width=True)

            if save_plan_btn:
                volume_plan.volume_title = v_title
                volume_plan.volume_logline = v_logline
                volume_plan.pacing_outline = v_pacing
                volume_plan.chapters = edited_chapters
                storage.save_volume_plan(slug, volume_plan)
                st.success("Volume Plan saved!")
                st.rerun()

            if approve_plan_btn:
                volume_plan.volume_title = v_title
                volume_plan.volume_logline = v_logline
                volume_plan.pacing_outline = v_pacing
                volume_plan.chapters = edited_chapters
                volume_plan.is_approved = True
                storage.save_volume_plan(slug, volume_plan)
                st.success("Volume Plan approved! You can now script individual chapters in Stage 3.")
                st.rerun()


# ==============================================================================
# TAB 3: CHAPTER SCRIPT
# ==============================================================================
with tabs[2]:
    st.subheader("🖋️ Stage 3: Chapter Scripting (Page by Page)")
    st.markdown("Generates full manga scripts with page layouts, panel sizes, camera angles, dialogue, and sound effects.")

    if not bible or not volume_plan:
        st.warning("⚠️ Please complete the Story Bible and Volume Plan before scripting chapters.")
        st.stop()

    # Chapter selector
    ch_numbers = list(range(1, settings.chapters_per_volume + 1))
    current_ch = st.selectbox(
        "Select Chapter to Script",
        options=ch_numbers,
        format_func=lambda x: f"Chapter {x}: {volume_plan.chapters[x-1].title if x <= len(volume_plan.chapters) else ''}",
    )

    script = storage.load_chapter_script(slug, current_ch)
    recap = storage.load_chapter_recap(slug, current_ch)

    if script:
        badge_cls = "badge-approved" if script.is_approved else "badge-draft"
        badge_txt = f"Chapter {current_ch} Approved" if script.is_approved else f"Chapter {current_ch} Draft"
        st.markdown(f'<span class="status-badge {badge_cls}">{badge_txt}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="status-badge badge-pending">Chapter {current_ch} Not Scripted Yet</span>', unsafe_allow_html=True)

    # Previous Chapters Context / Recaps
    previous_recaps = storage.get_all_previous_recaps(slug, current_ch)
    with st.expander(f"📜 Story Continuity: Previous Recaps ({len(previous_recaps)} earlier chapters)", expanded=False):
        if previous_recaps:
            for ch_idx, rtext in previous_recaps.items():
                st.markdown(f"**Chapter {ch_idx} Recap:**")
                st.markdown(rtext)
                st.divider()
        else:
            st.info("No prior chapters. This is the opening chapter.")

    # Generator Section
    with st.expander(f"✨ Script Chapter {current_ch} with AI", expanded=(script is None)):
        ch_user_notes = st.text_area(
            "Specific Directorial / Pacing Notes for this Chapter",
            value="Emphasize dramatic close-ups and dynamic speed lines. Ensure dialogue is punchy and impactful.",
            height=70,
        )
        if st.button(f"Generate Script for Chapter {current_ch}", type="primary", use_container_width=True):
            with st.spinner(f"Writing Chapter {current_ch} script page by page..."):
                try:
                    new_script = generate_chapter_script(
                        settings,
                        bible,
                        volume_plan,
                        current_ch,
                        provider,
                        previous_recaps=previous_recaps,
                        user_notes=ch_user_notes,
                    )
                    storage.save_chapter_script(slug, current_ch, new_script)
                    st.success(f"Chapter {current_ch} script generated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating chapter script: {e}")

    # Script Viewer and Human Approval
    if script:
        st.markdown(f"### {script.title}")
        st.markdown(f"*{script.summary}*")

        if recap:
            with st.expander("📝 Auto-generated Chapter Recap (recap.md)", expanded=False):
                st.markdown(recap)

        # Display Pages and Panels
        for p_idx, page in enumerate(script.pages):
            with st.expander(f"📄 Page {page.page_number} ({len(page.panels)} panels) — {page.page_notes}", expanded=(p_idx == 0)):
                for panel in page.panels:
                    st.markdown(
                        f"""
                        <div class="panel-card">
                            <b>Panel {panel.panel_number}</b> | Size: <code>{panel.panel_size.value}</code> | Angle: <i>{panel.camera_angle}</i><br/>
                            <b>Scene:</b> {panel.description}<br/>
                            <b>Characters:</b> {", ".join(panel.characters_present) if panel.characters_present else "None"}<br/>
                            <b>Pacing Note:</b> {panel.pacing_notes or "Standard"}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    # Dialogue
                    if panel.dialogue:
                        for d in panel.dialogue:
                            d_icon = "💬" if d.type != BubbleType.SFX else "💥"
                            st.write(f"{d_icon} **{d.speaker}** ({d.type.value}): \"{d.text}\"")

        # Approval and Recap Generation
        st.divider()
        col_app1, col_app2 = st.columns([1, 1])
        with col_app1:
            if not script.is_approved:
                if st.button(f"✅ Approve Chapter {current_ch} & Generate Recap", type="primary", use_container_width=True):
                    with st.spinner("Approving chapter and synthesizing recap.md..."):
                        script.is_approved = True
                        storage.save_chapter_script(slug, current_ch, script)
                        # Auto-generate recap
                        recap_content = generate_chapter_recap(script, provider)
                        storage.save_chapter_recap(slug, current_ch, recap_content)
                        st.success(f"Chapter {current_ch} approved and recap.md saved! Story brain updated.")
                        st.rerun()
            else:
                st.success("✅ This chapter is approved! Its recap is locked into story continuity.")
        with col_app2:
            if st.button("🔄 Regenerate Recap from Script", use_container_width=True):
                with st.spinner("Synthesizing recap..."):
                    recap_content = generate_chapter_recap(script, provider)
                    storage.save_chapter_recap(slug, current_ch, recap_content)
                    st.success("recap.md updated!")
                    st.rerun()


# ==============================================================================
# TAB 4: ART & PANEL GALLERY (PHASE 2)
# ==============================================================================
with tabs[3]:
    st.subheader("🖼️ Stage 4: Art & Panel Gallery")
    st.markdown(
        "Generate and manage manga panel artwork with automatic locked character descriptors, "
        "deterministic SHA-256 caching (zero token reruns), seed locking, and cost-guard confirmations."
    )

    if not bible or not volume_plan:
        st.warning("⚠️ Please complete the Story Bible and Volume Plan before generating panel artwork.")
        st.stop()

    # Chapter selection for panel gallery
    art_ch_numbers = list(range(1, settings.chapters_per_volume + 1))
    art_ch = st.selectbox(
        "Select Chapter for Artwork",
        options=art_ch_numbers,
        key="art_chapter_select",
        format_func=lambda x: f"Chapter {x}: {volume_plan.chapters[x-1].title if x <= len(volume_plan.chapters) else ''}",
    )

    art_script = storage.load_chapter_script(slug, art_ch)
    if not art_script:
        st.warning(f"⚠️ Chapter {art_ch} has not been scripted yet. Please generate its script in Stage 3 first.")
        st.stop()

    manifest = storage.load_panels_manifest(slug, art_ch)
    cost_info = estimate_generation_cost(storage, slug, art_ch, art_script)
    total_panels = cost_info["total_panels"]
    existing_panels = cost_info["existing_panels"]
    pending_calls = cost_info["pending_calls"]

    # --- Progress Header ---
    st.markdown(f"### Chapter {art_ch}: {art_script.title}")
    pct_complete = (existing_panels / total_panels) if total_panels > 0 else 0.0
    st.progress(pct_complete, text=f"Panels Generated: {existing_panels} of {total_panels} ({int(pct_complete * 100)}%)")

    # --- Cost Guard & Batch Generation Box ---
    with st.expander("⚡ Batch Generation & Cost Guard", expanded=(pending_calls > 0 and existing_panels == 0)):
        st.markdown(
            f"""
            <div style="background-color: rgba(245, 158, 11, 0.08); border-left: 4px solid #f59e0b; padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem;">
                <b>🛡️ Cost-Guard Estimate</b><br/>
                • Total panels in script: <b>{total_panels}</b><br/>
                • Existing generated / cached: <b>{existing_panels}</b> (Zero API cost)<br/>
                • New API calls required: <b>{pending_calls}</b> (via <i>{img_choice}</i>)
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_bg1, col_bg2 = st.columns([1, 1])
        with col_bg1:
            force_regenerate = st.checkbox("Force regenerate all panels (overwrite existing images)", value=False)
        with col_bg2:
            calls_to_make = total_panels if force_regenerate else pending_calls
            confirm_guard = st.checkbox(
                f"I approve generating {calls_to_make} panels with {img_choice}",
                value=(calls_to_make == 0),
            )

        if st.button("🚀 Run Batch Panel Generation", type="primary", disabled=not confirm_guard, use_container_width=True):
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            def update_progress(curr, tot, msg):
                frac = curr / tot if tot > 0 else 1.0
                progress_bar.progress(frac)
                status_text.caption(f"Generating ({curr}/{tot}): {msg}")

            try:
                results = batch_generate_chapter_panels(
                    storage=storage,
                    slug=slug,
                    chapter_number=art_ch,
                    script=art_script,
                    bible=bible,
                    settings=settings,
                    provider=image_provider,
                    force_refresh=force_regenerate,
                    progress_callback=update_progress,
                )
                st.success(
                    f"Batch generation complete! Generated {results['new_generations']} new panels, "
                    f"reused {results['cache_hits']} cached panels."
                )
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error during batch generation: {e}")

    st.divider()

    # --- Filter by Page ---
    page_options = ["All Pages"] + [f"Page {p.page_number}" for p in art_script.pages]
    selected_page_filter = st.selectbox("Filter Panels by Page", options=page_options)

    # --- Panel Cards Gallery ---
    for page in art_script.pages:
        page_label = f"Page {page.page_number}"
        if selected_page_filter != "All Pages" and selected_page_filter != page_label:
            continue

        st.markdown(f"#### 📄 {page_label} ({len(page.panels)} panels) — *{page.page_notes or 'Layout Beat'}*")

        for panel in page.panels:
            panel_id = f"p{page.page_number}_panel{panel.panel_number}"
            img_path = storage.get_panel_image_path(slug, art_ch, panel_id)
            meta = manifest.panels.get(panel_id)
            img_exists = img_path.exists()

            # Compile prompt for preview and potential override
            prompt_bundle = build_panel_image_prompt(panel, bible, settings)
            current_prompt = meta.prompt if meta else prompt_bundle["prompt"]
            w, h = get_panel_dimensions(panel.panel_size)

            with st.container():
                st.markdown(f'<div class="panel-card">', unsafe_allow_html=True)
                col_img, col_ctrl = st.columns([1, 1])

                # Left Column: Image Artwork Preview
                with col_img:
                    if img_exists:
                        st.image(str(img_path), caption=f"{panel_id} ({w}x{h})", use_container_width=True)
                        with open(img_path, "rb") as f_img:
                            st.download_button(
                                label="📥 Download PNG",
                                data=f_img.read(),
                                file_name=f"{slug}_ch{art_ch:02d}_{panel_id}.png",
                                mime="image/png",
                                key=f"dl_{panel_id}",
                                use_container_width=True,
                            )
                    else:
                        st.markdown(
                            f"""
                            <div style="border: 2px dashed #9ca3af; border-radius: 8px; height: 260px; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.02); text-align: center; padding: 1rem;">
                                <div>
                                    <span style="font-size: 2rem;">🖼️</span><br/>
                                    <b>Panel Not Generated Yet</b><br/>
                                    <small>{w}x{h} ({panel.panel_size.value})</small>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                # Right Column: Metadata, Seed & Regeneration Controls
                with col_ctrl:
                    # Status Badge
                    if img_exists and meta:
                        st.markdown(
                            f'<span class="status-badge badge-approved">Generated (Cache Key: {meta.cache_hash[:8]}...)</span>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown('<span class="status-badge badge-draft">Awaiting Generation</span>', unsafe_allow_html=True)

                    st.markdown(f"**Size:** `{panel.panel_size.value}` ({w}x{h} px) | **Camera:** *{panel.camera_angle}*")
                    if panel.characters_present:
                        st.markdown(f"**Characters:** `{', '.join(panel.characters_present)}`")

                    # Prompt editor / override
                    edited_prompt = st.text_area(
                        "Prompt (Enriched with Style & Character Descriptors)",
                        value=current_prompt,
                        key=f"prompt_edit_{panel_id}",
                        height=100,
                    )

                    with st.expander("Negative Prompt (Enforcing no text)", expanded=False):
                        st.caption(prompt_bundle["negative_prompt"])

                    # Seed & Lock-Seed Controls
                    col_seed1, col_seed2 = st.columns([1, 1])
                    curr_seed = meta.seed if meta and meta.seed is not None else random.randint(100000, 999999)
                    curr_locked = meta.seed_locked if meta else False

                    with col_seed1:
                        target_seed = st.number_input(
                            "Seed",
                            value=int(curr_seed),
                            key=f"seed_input_{panel_id}",
                            step=1,
                        )
                    with col_seed2:
                        st.write("") # spacing
                        st.write("")
                        is_locked = st.checkbox("🔒 Lock Seed", value=curr_locked, key=f"lock_seed_{panel_id}")

                    # Regenerate / Generate Button
                    btn_label = "🔄 Regenerate Panel" if img_exists else "✨ Generate Panel"
                    if st.button(btn_label, key=f"regen_{panel_id}", type="primary", use_container_width=True):
                        with st.spinner(f"Rendering {panel_id}..."):
                            try:
                                new_meta, is_hit = generate_panel_image(
                                    storage=storage,
                                    slug=slug,
                                    chapter_number=art_ch,
                                    page_number=page.page_number,
                                    panel=panel,
                                    bible=bible,
                                    settings=settings,
                                    provider=image_provider,
                                    seed=int(target_seed),
                                    seed_locked=is_locked,
                                    prompt_override=edited_prompt,
                                    force_refresh=True,
                                )
                                msg = f"Panel {panel_id} rendered! ({'Cache Hit - 0 cost' if is_hit else 'Fresh Generation'})"
                                st.success(msg)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Generation failed: {e}")

                st.markdown("</div>", unsafe_allow_html=True)
                st.write("") # spacing

# ==============================================================================
# TAB 5: PAGE COMPOSER & LETTERING STUDIO (PHASE 3)
# ==============================================================================
with tabs[4]:
    st.subheader("💬 Stage 5: Page Composer & Lettering Studio")
    st.markdown(
        "Assemble script panels into a print-ready grid (RTL/LTR) at 300 DPI with 3mm bleed. "
        "Draw speech, thought, shout, whisper, and SFX bubbles with automatic text wrapping and tails. "
        "Lettering remains an **editable overlay in JSON**: edit text and nudge coordinates with **zero artwork re-generation**."
    )

    if not bible or not volume_plan:
        st.warning("⚠️ Please complete the Story Bible and Volume Plan before composing pages.")
        st.stop()

    comp_ch_numbers = list(range(1, settings.chapters_per_volume + 1))
    comp_ch = st.selectbox(
        "Select Chapter for Page Composition",
        options=comp_ch_numbers,
        key="comp_chapter_select",
        format_func=lambda x: f"Chapter {x}: {volume_plan.chapters[x-1].title if x <= len(volume_plan.chapters) else ''}",
    )

    comp_script = storage.load_chapter_script(slug, comp_ch)
    if not comp_script:
        st.warning(f"⚠️ Chapter {comp_ch} has not been scripted yet. Please generate its script in Stage 3 first.")
        st.stop()

    # --- Page Selector & Global Layout Controls ---
    col_p1, col_p2, col_p3 = st.columns([1, 1, 1])
    with col_p1:
        page_nums = [p.page_number for p in comp_script.pages]
        selected_page_num = st.selectbox(
            "Select Page",
            options=page_nums,
            format_func=lambda x: f"Page {x} ({len(comp_script.pages[x-1].panels)} panels)" if x <= len(comp_script.pages) else f"Page {x}",
        )
    with col_p2:
        show_guides_toggle = st.checkbox("📐 Safe-Margin & Bleed Overlay", value=False, help="Show 3mm bleed line (red), trim (black), and 10mm safe margin (cyan).")
    with col_p3:
        reading_dir = st.radio("Reading Order", ["RTL (Japanese Manga)", "LTR (Western Comic)"], index=0 if settings.reading_direction == "RTL" else 1, horizontal=True)
        settings.reading_direction = "RTL" if "RTL" in reading_dir else "LTR"

    target_page_script = None
    for p in comp_script.pages:
        if p.page_number == selected_page_num:
            target_page_script = p
            break

    if not target_page_script:
        st.error(f"Page {selected_page_num} not found.")
        st.stop()

    # Load or initialize lettering overlay for this page
    lettering_dict = storage.load_page_lettering(slug, comp_ch, selected_page_num)
    geometry = calculate_canvas_geometry(settings)
    canvas_w = geometry["canvas_width"]
    canvas_h = geometry["canvas_height"]

    if lettering_dict is None:
        # Default initialization from dialogue items in target_page_script
        default_bubbles = []
        for p_idx, panel in enumerate(target_page_script.panels):
            for d_idx, d in enumerate(panel.dialogue):
                default_bubbles.append({
                    "bubble_id": f"p{selected_page_num}_panel{panel.panel_number}_b{d_idx+1}",
                    "panel_number": panel.panel_number,
                    "speaker": d.speaker,
                    "text": d.text,
                    "type": d.type.value,
                    "tail_position": d.tail_position or "bottom-center",
                    "center_x": int(canvas_w * (0.35 if d_idx % 2 == 0 else 0.65)),
                    "center_y": int(canvas_h * (0.2 + (p_idx * 0.28) + (d_idx * 0.12))),
                    "font_size": 28,
                })
        lettering_dict = {"page_number": selected_page_num, "bubbles": default_bubbles}
        storage.save_page_lettering(slug, comp_ch, selected_page_num, lettering_dict)

    # Two column workspace: Live Page Preview (Left) vs Lettering Controls (Right)
    col_preview, col_editor = st.columns([1, 1])

    # Compose live page image
    live_page_img = compose_single_page(
        slug=slug,
        chapter_number=comp_ch,
        page_script=target_page_script,
        storage=storage,
        settings=settings,
        lettering_data=lettering_dict,
        show_guides=show_guides_toggle,
    )

    with col_preview:
        st.markdown(f"#### 📖 Page {selected_page_num} Print Preview")
        st.image(live_page_img, caption=f"Page {selected_page_num} ({canvas_w}x{canvas_h} px @ 300 DPI)", use_container_width=True)

        col_save_p1, col_save_p2 = st.columns([1, 1])
        with col_save_p1:
            if st.button("💾 Save Composed Page PNG", type="primary", use_container_width=True):
                out_p = compose_and_save_page(
                    slug=slug,
                    chapter_number=comp_ch,
                    page_script=target_page_script,
                    storage=storage,
                    settings=settings,
                    lettering_data=lettering_dict,
                    show_guides=False,
                )
                st.success(f"Saved composed page to {out_p.name}!")
        with col_save_p2:
            import io
            buf_page = io.BytesIO()
            live_page_img.save(buf_page, format="PNG")
            st.download_button(
                label="📥 Download Page PNG",
                data=buf_page.getvalue(),
                file_name=f"{slug}_ch{comp_ch:02d}_page_{selected_page_num:02d}.png",
                mime="image/png",
                use_container_width=True,
            )

        if st.button("⚡ Compose All Pages in Chapter", use_container_width=True):
            with st.spinner("Composing full chapter print pages..."):
                saved_count = 0
                for p in comp_script.pages:
                    p_let = storage.load_page_lettering(slug, comp_ch, p.page_number)
                    compose_and_save_page(
                        slug=slug,
                        chapter_number=comp_ch,
                        page_script=p,
                        storage=storage,
                        settings=settings,
                        lettering_data=p_let,
                        show_guides=False,
                    )
                    saved_count += 1
                st.success(f"All {saved_count} pages in Chapter {comp_ch} composed and saved to `pages/` folder!")

    with col_editor:
        st.markdown("#### ✏️ Lettering & Dialogue Editor")
        st.caption("Nudge bubbles and edit dialogue text. Updates immediately without re-rendering artwork.")

        with st.form("lettering_editor_form"):
            updated_bubbles = []
            for b_idx, b in enumerate(lettering_dict.get("bubbles", [])):
                st.markdown(f"**Bubble #{b_idx+1}: {b.get('speaker', 'Speaker')}** (Panel {b.get('panel_number', 1)})")
                b_text = st.text_area(
                    "Dialogue / Sound Effect Text",
                    value=b.get("text", ""),
                    key=f"let_text_{selected_page_num}_{b_idx}",
                    height=65,
                )

                col_b1, col_b2, col_b3 = st.columns([1, 1, 1])
                with col_b1:
                    type_options = ["speech", "thought", "shout", "whisper", "sfx", "narrator"]
                    curr_type = b.get("type", "speech").lower()
                    b_type = st.selectbox(
                        "Bubble Style",
                        type_options,
                        index=type_options.index(curr_type) if curr_type in type_options else 0,
                        key=f"let_type_{selected_page_num}_{b_idx}",
                    )
                with col_b2:
                    tail_options = ["bottom-center", "bottom-left", "bottom-right", "top-left", "top-right"]
                    curr_tail = b.get("tail_position", "bottom-center").lower()
                    b_tail = st.selectbox(
                        "Tail Direction",
                        tail_options,
                        index=tail_options.index(curr_tail) if curr_tail in tail_options else 0,
                        key=f"let_tail_{selected_page_num}_{b_idx}",
                    )
                with col_b3:
                    b_font_size = st.slider(
                        "Font Size (px)",
                        min_value=16,
                        max_value=56,
                        value=int(b.get("font_size", 28)),
                        step=2,
                        key=f"let_font_{selected_page_num}_{b_idx}",
                    )

                # Sliders to nudge X and Y
                col_pos1, col_pos2 = st.columns([1, 1])
                with col_pos1:
                    b_x = st.slider(
                        "Horizontal X Position",
                        min_value=50,
                        max_value=canvas_w - 50,
                        value=int(b.get("center_x", canvas_w // 2)),
                        step=10,
                        key=f"let_x_{selected_page_num}_{b_idx}",
                    )
                with col_pos2:
                    b_y = st.slider(
                        "Vertical Y Position",
                        min_value=50,
                        max_value=canvas_h - 50,
                        value=int(b.get("center_y", canvas_h // 2)),
                        step=10,
                        key=f"let_y_{selected_page_num}_{b_idx}",
                    )

                updated_bubbles.append({
                    "bubble_id": b.get("bubble_id", f"b_{b_idx+1}"),
                    "panel_number": b.get("panel_number", 1),
                    "speaker": b.get("speaker", "Character"),
                    "text": b_text,
                    "type": b_type,
                    "tail_position": b_tail,
                    "center_x": b_x,
                    "center_y": b_y,
                    "font_size": b_font_size,
                })
                st.divider()

            save_lettering_btn = st.form_submit_button("💾 Save Lettering Changes & Recompose", type="primary", use_container_width=True)

            if save_lettering_btn:
                lettering_dict["bubbles"] = updated_bubbles
                storage.save_page_lettering(slug, comp_ch, selected_page_num, lettering_dict)
                st.success("Lettering overlay updated and recomposed!")
                st.rerun()

        # Add new bubble button
        if st.button("➕ Add New Dialogue / SFX Bubble", use_container_width=True):
            new_b = {
                "bubble_id": f"p{selected_page_num}_custom_{len(lettering_dict.get('bubbles', []))+1}",
                "panel_number": 1,
                "speaker": "Ren",
                "text": "New dialogue line",
                "type": "speech",
                "tail_position": "bottom-center",
                "center_x": canvas_w // 2,
                "center_y": canvas_h // 2,
                "font_size": 28,
            }
            lettering_dict.setdefault("bubbles", []).append(new_b)
            storage.save_page_lettering(slug, comp_ch, selected_page_num, lettering_dict)
            st.success("Added new bubble! Adjust its position and text above.")
            st.rerun()

# ==============================================================================
# TAB 6: EXPORT STUDIO (PHASE 4)
# ==============================================================================
with tabs[5]:
    st.subheader("📦 Stage 6: Export Studio (Print Tankobon & Webtoon Slices)")
    st.markdown(
        "Generate distribution-ready manga packages: "
        "**Print Tankobon PDF** (with 4-page signature padding and 3mm bleed) and "
        "**Webtoon 800px Vertical Strip** (with non-destructive gap slicing and automated file limit audits)."
    )

    if not bible or not volume_plan:
        st.warning("⚠️ Please complete earlier stages before exporting.")
        st.stop()

    export_mode_tabs = st.tabs(["🖨️ PRINT Tankobon Export", "📱 WEBTOON Vertical Slices"])

    # --------------------------------------------------------------------------
    # SUB-TAB 1: PRINT TANKOBON EXPORT
    # --------------------------------------------------------------------------
    with export_mode_tabs[0]:
        st.markdown("### 🖨️ Print Tankobon PDF & Page Image Compilation")
        st.caption("Compiles all composed pages, pads total count to a multiple of 4, and builds a print-ready PDF with bleed.")

        col_pr1, col_pr2 = st.columns([1, 1])
        with col_pr1:
            scope_choice = st.radio(
                "Export Scope",
                ["Full Volume (All Chapters)", "Single Chapter"],
                index=0,
                horizontal=True,
            )
            ch_filter = None
            if scope_choice == "Single Chapter":
                ch_filter = st.selectbox(
                    "Select Chapter to Export",
                    options=list(range(1, settings.chapters_per_volume + 1)),
                    key="print_ch_filter",
                )

        with col_pr2:
            pad_sig = st.checkbox(
                "Pad Total Pages to Multiple of 4 (Signature Binding)",
                value=True,
                help="Appends blank pages so the document can be folded and bound into physical booklets.",
            )
            rev_order = st.checkbox(
                "Reverse Page Order (Right-to-Left Physical Binding)",
                value=False,
                help="Check if your print-on-demand service requires pages ordered from back-to-front for Japanese right-to-left binding.",
            )

        if st.button("🚀 Export Print Tankobon PDF & PNGs", type="primary", use_container_width=True):
            with st.spinner("Assembling print pages, verifying signature padding, and generating PDF..."):
                try:
                    res = export_print_volume(
                        slug=slug,
                        storage=storage,
                        settings=settings,
                        reverse_order=rev_order,
                        pad_signature=pad_sig,
                        chapter_filter=ch_filter,
                    )
                    st.success(
                        f"🎉 Print export complete! "
                        f"Compiled {res['original_pages']} pages + {res['blank_added']} blank padding pages = "
                        f"**{res['total_pages']} total pages (Multiple of 4: ✅)**."
                    )
                    st.session_state["last_print_export"] = res
                except Exception as e:
                    st.error(f"Print export failed: {e}")

        # Display results and direct download button
        if "last_print_export" in st.session_state:
            last_pr = st.session_state["last_print_export"]
            pdf_path: Path = last_pr["pdf_path"]
            if pdf_path.exists():
                st.markdown(
                    f"""
                    <div class="manga-card">
                        <b>📄 Print Package Ready:</b> <code>{pdf_path.name}</code><br/>
                        • Total Pages: <b>{last_pr['total_pages']}</b> (Original: {last_pr['original_pages']}, Blank Added: {last_pr['blank_added']})<br/>
                        • Page Canvas: <b>{last_pr['canvas_size_mm'][0]} x {last_pr['canvas_size_mm'][1]} mm</b> ({last_pr['canvas_size_px'][0]} x {last_pr['canvas_size_px'][1]} px @ 300 DPI)<br/>
                        • Reverse Order: <b>{'Yes (RTL)' if last_pr['reverse_order'] else 'No (Standard 1 to N)'}</b><br/>
                        • File Size: <b>{round(pdf_path.stat().st_size / (1024 * 1024), 2)} MB</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with open(pdf_path, "rb") as f_pdf:
                    st.download_button(
                        label="📥 Download Print-Ready PDF",
                        data=f_pdf.read(),
                        file_name=pdf_path.name,
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                    )

    # --------------------------------------------------------------------------
    # SUB-TAB 2: WEBTOON VERTICAL SLICES
    # --------------------------------------------------------------------------
    with export_mode_tabs[1]:
        st.markdown("### 📱 Webtoon Vertical Strip Layout & Slicer")
        st.caption("Lays out chapter panels into an 800px vertical strip, slices strictly through empty gap rows ($\le 1280$ px), and packages a ZIP.")

        col_w1, col_w2, col_w3 = st.columns([1, 1, 1])
        with col_w1:
            webtoon_ch = st.selectbox(
                "Select Episode / Chapter",
                options=list(range(1, settings.chapters_per_volume + 1)),
                key="webtoon_ch_select",
                format_func=lambda x: f"Chapter {x}: {volume_plan.chapters[x-1].title if x <= len(volume_plan.chapters) else ''}",
            )
        with col_w2:
            slice_format = st.selectbox("Image Format", ["PNG", "JPG (Quality 92)"])
        with col_w3:
            webtoon_gap = st.slider("Panel Gap Spacing (px)", min_value=40, max_value=200, value=90, step=10)

        webtoon_script = storage.load_chapter_script(slug, webtoon_ch)
        if not webtoon_script:
            st.warning(f"Chapter {webtoon_ch} has not been scripted yet.")
        else:
            if st.button("📱 Lay Out & Slice Webtoon Episode", type="primary", use_container_width=True):
                with st.spinner("Building 800px vertical strip and non-destructively slicing..."):
                    try:
                        w_res = export_webtoon_chapter(
                            slug=slug,
                            chapter_number=webtoon_ch,
                            script=webtoon_script,
                            storage=storage,
                            settings=settings,
                            img_format="JPG" if "JPG" in slice_format else "PNG",
                            gap_px=webtoon_gap,
                        )
                        st.session_state["last_webtoon_export"] = w_res
                        st.success(f"Webtoon episode exported into {w_res['slice_count']} slices!")
                    except Exception as e:
                        st.error(f"Webtoon export failed: {e}")

            if "last_webtoon_export" in st.session_state:
                w_res = st.session_state["last_webtoon_export"]
                zip_path: Path = w_res["zip_path"]

                # Warnings Alert
                if w_res["warnings"]:
                    for w_msg in w_res["warnings"]:
                        st.warning(f"⚠️ {w_msg}")

                st.markdown(
                    f"""
                    <div class="manga-card">
                        <b>📦 Webtoon Archive Ready:</b> <code>{zip_path.name}</code><br/>
                        • Strip Resolution: <b>800 x {w_res['total_height_px']} px</b><br/>
                        • Slice Count: <b>{w_res['slice_count']} images</b> (Limit: 100 max)<br/>
                        • Archive Size: <b>{w_res['total_mb']} MB</b> (Limit: 20 MB max)<br/>
                        • Slice Height Limit: <b>$\le 1280$ px (Cuts strictly in empty gutters)</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if zip_path.exists():
                    with open(zip_path, "rb") as f_zip:
                        st.download_button(
                            label=f"📥 Download Webtoon ZIP ({w_res['total_mb']} MB)",
                            data=f_zip.read(),
                            file_name=zip_path.name,
                            mime="application/zip",
                            type="primary",
                            use_container_width=True,
                        )

                # Visual Slices Gallery Preview
                with st.expander(f"👀 Preview Slices ({w_res['slice_count']} images)", expanded=False):
                    for idx, sf in enumerate(w_res["slice_files"]):
                        st.markdown(f"**Slice #{idx+1:03d}** ({sf.name})")
                        st.image(str(sf), use_container_width=True)


