# Brief Forge 🎨

> Transform plain-language design goals into structured, actionable creative briefs — powered by GPT-4o.

Brief Forge bridges the communication gap between **non-designers who know what they want** and the design tools that need precise creative direction.  Describe your idea in everyday language and get back a complete design specification with layout suggestions, colour palettes (with hex codes), typography pairings, copy hierarchy, and mood descriptors — all formatted for easy paste into **Canva**, **Figma**, or **Adobe** tools.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Plain-language input** | Describe your project in plain English — no design jargon required. |
| **Structured brief output** | Every brief contains layout, colour palette, typography, copy hierarchy, and mood sections. |
| **Visual colour swatches** | Hex codes are rendered as clickable, copyable colour swatches directly in the browser. |
| **Multiple export formats** | Copy the brief as **Markdown**, **plain text**, or **JSON** for use in any design workflow. |
| **Pydantic-validated output** | GPT-4o responses are parsed and validated so every field is always present. |
| **Stateless & instant** | No database, no accounts — generate, copy, and go. |

---

## 🚀 Quick Start

### Prerequisites

- Python **3.11** or newer
- An [OpenAI API key](https://platform.openai.com/api-keys) with access to `gpt-4o`
- `pip` (or `uv` / `pipx` — your preference)

### 1 — Clone the repository

```bash
git clone https://github.com/your-org/brief_forge.git
cd brief_forge
```

### 2 — Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3 — Install dependencies

```bash
pip install -e ".[dev]"
```

### 4 — Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```dotenv
OPENAI_API_KEY=sk-your-real-key-here
FLASK_SECRET_KEY=a-long-random-string
```

### 5 — Run the development server

```bash
flask --app brief_forge.app run --debug
```

Or using the installed entry point:

```bash
briefforge
```

Open your browser at **http://127.0.0.1:5000**.

---

## 🖥️ Usage

1. **Describe your project** in the text area.  The more context you give, the richer the brief.  Example prompts are shown below.
2. Click **"Generate Brief"**.
3. Review the structured brief — colour swatches, typography stack, layout grid, and copy hierarchy are all rendered inline.
4. Use the **Copy** buttons to export as Markdown, plain text, or JSON.
5. Paste directly into Figma (Plugins → Paste Clipboard), Canva (Notes / Brand Kit), or an Adobe brief document.

---

## 📝 Example Input / Output

### Input

```
I need a landing page for a sustainable coffee brand aimed at millennials.
The vibe should feel earthy and premium but not pretentious — think warm
neutrals, natural textures, and a hint of sage green.  The hero headline
is "Good coffee. Good planet."  We want people to sign up for a
subscription box.
```

### Output (excerpt)

```markdown
# Design Brief — Sustainable Coffee Landing Page

## Project Overview
A conversion-focused landing page for a sustainable, premium coffee
subscription brand targeting environmentally-conscious millennials.

## Mood & Tone
Earthy · Premium · Approachable · Conscious · Warm

## Colour Palette
| Role        | Name            | Hex       | Usage                     |
|-------------|-----------------|-----------|---------------------------|
| Primary     | Espresso Brown  | `#3B2314` | Headlines, CTAs           |
| Secondary   | Sage Green      | `#7D9B76` | Accents, icon fills       |
| Background  | Oat Cream       | `#F5EFE6` | Page background           |
| Surface     | Warm Sand       | `#E8D9C5` | Card backgrounds          |
| Text        | Dark Roast      | `#1A1008` | Body copy                 |

## Typography
- **Display / Headlines:** Playfair Display (serif) — weight 700
- **Body copy:** Inter (sans-serif) — weight 400 / 500
- **Accent / Labels:** Playfair Display Italic — weight 400

## Layout
- Single-column hero with full-bleed background texture image
- Hero: Large display headline + sub-headline + single CTA button
- Social proof strip: 3-icon value proposition row
- Product showcase: Alternating image/text rows (50/50 grid)
- Email capture section: Centred, minimal — first name + email + CTA
- Footer: Logo · Nav links · Social icons

## Copy Hierarchy
1. **Hero Headline (H1):** "Good coffee. Good planet."
2. **Sub-headline (H2):** "Ethically sourced. Carbon-neutral shipping. Delivered monthly."
3. **CTA Button:** "Start My Subscription"
4. **Value Props:** Organic · B-Corp Certified · 1% for the Planet
5. **Section Headline:** "How it works" / "Choose your roast"
```

---

## 🧪 Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=brief_forge --cov-report=term-missing
```

---

## 🗂️ Project Structure

```
brief_forge/
├── __init__.py          # Package init — exposes create_app()
├── app.py               # Flask factory + routes
├── generator.py         # OpenAI prompt building + response parsing
├── models.py            # Pydantic models (DesignBrief, ColorPalette, …)
├── formatter.py         # Markdown / text / JSON rendering
├── templates/
│   ├── index.html       # Main single-page UI
│   └── brief_partial.html  # Reusable brief result component
└── static/
    └── style.css        # Responsive stylesheet with swatch rendering
tests/
├── test_generator.py
├── test_formatter.py
└── test_models.py
pyproject.toml
.env.example
README.md
```

---

## ⚙️ Configuration Reference

All configuration is via environment variables (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key. |
| `OPENAI_MODEL` | `gpt-4o` | Model used for generation. |
| `OPENAI_MAX_TOKENS` | `2048` | Maximum tokens per response. |
| `OPENAI_TEMPERATURE` | `0.7` | Sampling temperature (0.0–2.0). |
| `FLASK_SECRET_KEY` | — | **Required.** Flask session signing key. |
| `FLASK_ENV` | `development` | `development` or `production`. |
| `FLASK_HOST` | `127.0.0.1` | Dev server bind host. |
| `FLASK_PORT` | `5000` | Dev server port. |

---

## 🤝 Contributing

1. Fork the repository and create a feature branch.
2. Make your changes with tests.
3. Run `pytest` and ensure all tests pass.
4. Open a pull request with a clear description.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
