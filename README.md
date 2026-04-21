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

Generate a secure secret key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
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

1. **Describe your project** in the text area.  The more context you give, the richer the brief.  Example prompts are pre-loaded in the UI.
2. Click **"Generate Brief"**.
3. Review the structured brief — colour swatches, typography stack, layout grid, and copy hierarchy are all rendered inline.  Click any **colour swatch** to copy its hex code to your clipboard.
4. Use the **Copy** buttons in the Export section to export as Markdown, Plain Text, or JSON.
5. Paste directly into Figma (Plugins → Paste Clipboard), Canva (Notes / Brand Kit), or an Adobe brief document.

---

## 📝 Example Input / Output

### Example Input

```
I need a landing page for a sustainable coffee brand aimed at millennials.
The vibe should feel earthy and premium but not pretentious — think warm
neutrals, natural textures, and a hint of sage green.  The hero headline
is "Good coffee. Good planet."  We want people to sign up for a
subscription box.
```

### Example Output (Markdown format)

```markdown
# Design Brief — Sustainable Coffee Landing Page

## Project Overview

A conversion-focused landing page for a sustainable, premium coffee
subscription brand targeting environmentally-conscious millennials aged 25–38.
The primary goal is to drive email sign-ups and trial subscription purchases.

## Mood & Tone

earthy · premium · approachable · conscious · warm

## Colour Palette

| Role       | Name           | Hex       | Usage                          |
|------------|----------------|-----------|--------------------------------|
| Primary    | Espresso Brown | `#3B2314` | Headlines, CTAs                |
| Secondary  | Sage Green     | `#7D9B76` | Accents, icon fills            |
| Background | Oat Cream      | `#F5EFE6` | Page background                |
| Surface    | Warm Sand      | `#E8D9C5` | Card backgrounds               |
| Text       | Dark Roast     | `#1A1008` | Body copy                      |

## Typography

- **Display / Headlines:** Playfair Display — weight 700
- **Body copy:** Inter — weight 400
- **Accent / Labels:** Playfair Display Italic
- **Notes:** Use 1.6 line-height for body copy; generous tracking on labels.

## Layout

Single-column hero with full-bleed background texture image.

**Grid:** 12-column, 24px gutter

**Page sections (in order):**

- Hero: Large display headline + sub-headline + single CTA button
- Social proof strip: 3-icon value proposition row
- Product showcase: Alternating image/text rows (50/50 grid)
- Email capture: Centred, minimal — first name + email + CTA
- Footer: Logo · Nav links · Social icons

**Spacing notes:** 80px section padding; 40px between cards.

## Copy Hierarchy

1. Hero Headline (H1): "Good coffee. Good planet."
2. Sub-headline (H2): "Ethically sourced. Carbon-neutral shipping. Delivered monthly."
3. CTA Button: "Start My Subscription"
4. Value Props: Organic · B-Corp Certified · 1% for the Planet
5. Section Headline: "How it works" / "Choose your roast"

## Additional Notes

Ensure the hero CTA button meets WCAG AA colour contrast against the Oat
Cream background.  Photography should feature real people enjoying coffee
outdoors — avoid sterile studio shots.  The brand voice is warm, informed,
and quietly confident.
```

---

## 📡 API Reference

Brief Forge exposes a lightweight JSON API used by the frontend.  You can also call it directly.

### `POST /generate`

Generate a structured design brief from a plain-language description.

**Request body (JSON):**
```json
{
  "description": "A landing page for a sustainable coffee brand..."
}
```

**Success response (200):**
```json
{
  "success": true,
  "brief": {
    "title": "Sustainable Coffee Landing Page",
    "project_overview": "...",
    "mood_descriptors": ["earthy", "premium", "warm"],
    "color_palette": { "swatches": [ ... ] },
    "typography": { "display_font": "Playfair Display", ... },
    "layout": { "description": "...", "sections": [ ... ] },
    "copy_hierarchy": [ ... ],
    "additional_notes": "..."
  },
  "formats": {
    "markdown": "# Design Brief — ...",
    "text":     "====...====",
    "json":     "{ \"title\": \"...\" }"
  }
}
```

**Error response:**
```json
{
  "success": false,
  "error": "The 'description' field is required.",
  "error_type": "missing_field"
}
```

| Status | Meaning |
|---|---|
| 200 | Brief generated successfully |
| 400 | Missing/empty/too-long description |
| 429 | OpenAI rate limit exceeded |
| 500 | Generation or configuration error |
| 502 | OpenAI API connection/timeout error |

---

### `POST /format`

Re-render an existing brief dict in a specific output format without re-generating.

**Request body (JSON):**
```json
{
  "brief":  { ... },
  "format": "markdown"
}
```

Supported `format` values: `markdown`, `text`, `json`.

**Success response (200):**
```json
{
  "success": true,
  "output": "# Design Brief — ...",
  "format": "markdown"
}
```

---

### `GET /health`

Simple health-check endpoint.

**Response (200):**
```json
{ "status": "ok", "version": "0.1.0" }
```

---

## 🧪 Running Tests

```bash
pytest
```

With coverage report:

```bash
pytest --cov=brief_forge --cov-report=term-missing
```

All tests use mocked OpenAI responses — no API key is required to run the test suite.

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
├── test_generator.py    # Generator module tests (mocked API)
├── test_formatter.py    # Formatter module tests
├── test_models.py       # Pydantic model validation tests
└── test_app.py          # Flask route and integration tests
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
| `FLASK_SECRET_KEY` | — | **Required in production.** Flask session signing key. |
| `FLASK_ENV` | `production` | `development` enables debug mode. |
| `FLASK_HOST` | `127.0.0.1` | Dev server bind host. |
| `FLASK_PORT` | `5000` | Dev server port. |

---

## 🚢 Deployment

Brief Forge is a standard WSGI application and can be deployed anywhere Python runs.

### Gunicorn (recommended)

```bash
pip install gunicorn
gunicorn "brief_forge:create_app()" --workers 2 --bind 0.0.0.0:8000
```

### Docker (example)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
CMD ["gunicorn", "brief_forge:create_app()", "--workers", "2", "--bind", "0.0.0.0:8000"]
```

Set `FLASK_ENV=production` and `FLASK_SECRET_KEY` as environment variables in your hosting platform.

### Platform-as-a-Service

Brief Forge works out-of-the-box on **Heroku**, **Railway**, **Render**, and **Fly.io** — just set the required environment variables and point your start command at `gunicorn`.

---

## 🤝 Contributing

1. Fork the repository and create a feature branch.
2. Make your changes with tests.
3. Run `pytest` and ensure all tests pass.
4. Open a pull request with a clear description of your changes.

Please follow the existing code style (PEP 8, type hints, docstrings) and keep functions focused and well-documented.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
