# MangaForge ⚡

**MangaForge** is a production-grade manga studio tool that designs and generates original manga volumes chapter-by-chapter, and exports them as print-ready tankobon PDFs or Webtoon vertical slices.

---

## 🛠️ Stack
- **Runtime**: Python 3.11+
- **Frontend**: Streamlit UI (fully responsive and optimized for mobile/phone screens)
- **Data Models**: Pydantic v2 (with automated JSON schema validation & 2-turn retry loops)
- **Story Brain / Text AI**: Claude via Anthropic Python SDK behind an extensible `TextProvider` interface (with `MockTextProvider` for full offline development and testing)
- **Image AI**: Swappable `ImageProvider` interface with `MockImageProvider` and `CustomImageProvider` stub
- **Imaging**: Pillow for panel placeholders, lettering, and slicing
- **Testing**: `pytest`

---

## 📁 Project Storage Structure
MangaForge operates with zero external databases; each manga project is persisted as a self-contained directory:

```
projects/<slug>/
  settings.json       # Title, genre, rating, mode (PRINT|WEBTOON|BOTH), style traits, trim size, bleed, DPI
  bible.json          # Logline, synopsis, world rules, character sheets with locked visual descriptors
  volume_plan.json    # Volume arc logline, pacing outline, chapter-by-chapter breakdowns
  chapters/
    ch01/
      script.json     # Pages, panels, dialogue, camera angles, SFX, pacing notes
      recap.md        # Auto-generated chapter recap feeding subsequent chapter generation
      panels/         # Generated panel artwork (Phase 2)
      pages/          # Composed print pages with lettering (Phase 3)
    ch02/
      ...
  exports/            # Print-ready PDFs and Webtoon zip packages (Phase 4)
```

---

## 🚀 Quickstart & Setup

### 1. Clone & Install Dependencies
```bash
git clone <repo-url>
cd Manga-AI
python -m pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your Anthropic API key (optional for offline testing):
```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-7-sonnet-20250219
```
*Note: If no API key is provided, MangaForge automatically falls back to the built-in `MockTextProvider`, allowing you to test the complete pipeline completely offline without consuming tokens.*

### 3. Run the App
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`. On a mobile device connected to the same Wi-Fi, open `http://<YOUR_LOCAL_IP>:8501`.

### 4. Run Unit Tests
```bash
python -m pytest
```

---

## ☁️ Deploying to Streamlit Community Cloud
1. Push your repository to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io/).
3. Click **New app**, select your repository, branch `main`, and main file `app.py`.
4. In **Advanced Settings -> Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ANTHROPIC_MODEL = "claude-3-7-sonnet-20250219"
   ```
5. Click **Deploy**.

---

## 🗺️ Roadmap & Phases
- [x] **Phase 1: Story Brain & Core Studio Foundation**
  - Storage Manager (filesystem project structure, slugification, JSON/Markdown persistence)
  - Pydantic models for Settings, Bible, Volume Plan, Chapter Scripts, Dialogue, and Recaps
  - Swappable TextProvider interface (`AnthropicTextProvider` with validation retry + `MockTextProvider`)
  - Stage 1: Generate & Edit Story Bible with locked character visual descriptors
  - Stage 2: Generate & Edit Volume Plan (chapter pacing breakdown)
  - Stage 3: Generate & Edit Chapter Scripts (pages, panels, dialogue, SFX) + Auto-generate `recap.md` on approval
  - Mobile-responsive Streamlit UI with progress tracking and status badges
- [x] **Phase 2: Image Provider & Panel Gallery Studio**
  - `ImageProvider` ABC, `MockImageProvider` (with screentones & metadata frames), and `CustomImageProvider` stub
  - Automated Enriched Prompt Compiler: Locked style traits + scene description + camera angles + locked character visual descriptors
  - Universal Negative Prompt: enforcing `"no text, no speech bubbles, no lettering"`
  - Deterministic SHA-256 caching by `(prompt, seed, width, height)` so reruns cost zero API tokens
  - Interactive Panel Gallery with per-panel **Regenerate**, prompt tweaking, **Seed Locking**, and single-click PNG download
  - Batch generation with live progress bars and **Cost-Guard** approval confirmation
- [x] **Phase 3: Page Composer & Lettering Studio**
  - Layout Grid Engine: Computes panel bounding boxes for 1 to 6+ panels with configurable gutters and reading order (**RTL Japanese Manga default** or LTR Western comic toggle)
  - Full print canvas at 300 DPI with 3mm bleed (128x182 mm B6 Tankobon standard) and 10mm inner safe text margin
  - Pillow Bubble & SFX Renderer: Speech, thought, shout (jagged starburst), whisper, SFX (impact drop shadow), and narrator boxes with automatic text wrapping and directional pointer tails
  - Bundled TrueType comic fonts (`ComicNeue`, `Impact`, `Comic Sans`, `Arial Bold`)
  - Interactive Lettering Overlay Editor: dialogue text editing and coordinate nudging `(x, y)` stored in JSON with **zero image re-generation required**
  - Single-page and full-chapter batch print composition with safe-margin overlay preview
- [x] **Phase 4: Print & Webtoon Export Engine**
  - **Print Tankobon PDF Assembler**:
    - Assembles composed pages across the full volume or by chapter.
    - **4-Page Signature Padding**: Automatically appends blank pages so total page count is a multiple of 4 ($4, 8, 12, 16, 20, \dots$) required for physical booklet binding.
    - **Right-to-Left (RTL) Binding Support**: Toggleable reverse-order page collation for traditional Japanese manga publishing.
    - Compiles high-resolution 300 DPI PDF with 3mm bleed via ReportLab.
    - Exports high-res numbered PNG folder (`page_001.png`, `page_002.png`, etc.).
  - **Webtoon 800px Vertical Strip & Slicer**:
    - Lays out each chapter into an **800 px wide continuous vertical strip** with customizable gap spacing.
    - **Non-Destructive Slicer Algorithm**: Slices into images of at most **1280 px tall**, cutting **strictly through whitespace gap rows** and **never through panels or text bubbles**.
    - Export format: PNG or JPG (quality 92).
    - Automatically packages numbered slices into a single ZIP archive per chapter (`<slug>_ch01_webtoon.zip`).
    - Automated Limit Audits: Warns if an episode exceeds **100 images** or **20 MB total**.
- [x] **Phase 5: Polish & Comprehensive End-to-End Suite**
  - Live Studio Progress Dashboard tracking volume milestones (Bible, Volume Plan, Chapters, Art, Pages, Exports)
  - Full end-to-end integration test suite (`tests/test_end_to_end.py`) verifying the complete lifecycle offline with MockProvider
  - Production-ready `requirements.txt` and Streamlit Community Cloud secrets configuration
  - Complete documentation and clean architecture across `core/`, `providers/`, `prompts/`, and `tests/`

---

## 📖 Publishing & Binding Guide

### 1. Print Tankobon Signature Binding & 4-Page Padding
Commercial books and manga tankobons are printed on large sheets folded into 4-page, 8-page, or 16-page signatures before binding. MangaForge automatically pads total document pages to a multiple of 4 ($4, 8, 12, 16, 20, \dots$) by appending blank pages with correct bleed dimensions.

### 2. Right-to-Left (RTL) vs. Left-to-Right (LTR) Collation
- **Authentic Japanese Manga (RTL)**: Readers open the book from the left (front cover on the right side) and read panels from right-to-left. In digital PDF readers that read forward, keep "Reverse Page Order" **unchecked**. If your print-on-demand service requires pre-collated back-to-front PDFs for binding, check **"Reverse Page Order (Right-to-Left Physical Binding)"** in Stage 6.
- **Western Comics / Manhwa (LTR)**: Use the LTR toggle in Stage 5 to flow panels and dialogue from left-to-right.

### 3. Webtoon Platform Standards (LINE Webtoon / Tapas)
- Width: Fixed **800 px wide**.
- Height per slice: Maximum **1280 px**.
- Non-destructive slicing: MangaForge slices strictly through whitespace gutter rows, never cutting through artwork or text bubbles.
- Automated safety audits: Alerts if an episode exceeds 100 images or 20 MB total.

---

## 📱 Mobile & Tablet Screen Usage
MangaForge features responsive styling optimized for touchscreens:
- **Responsive Navigation**: Touch targets formatted to minimum 44px height for mobile devices.
- **Split-View Adaptability**: Controls stack into vertical cards on screens $\le 768\text{ px}$.
- **Remote Access**: Connect your phone to the same local Wi-Fi and open `http://<YOUR_COMPUTER_LOCAL_IP>:8501`.

