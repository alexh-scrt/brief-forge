# Brief Forge 🎨

> Transform plain-language design goals into structured, actionable creative briefs — powered by GPT-4o.

Brief Forge bridges the communication gap between **non-designers who know what they want** and the design tools that need precise creative direction. Describe your idea in everyday language and get back a complete design specification — layout suggestions, color palettes with hex codes, typography pairings, copy hierarchy, and mood descriptors — all formatted for easy paste into **Canva**, **Figma**, or **Adobe** tools.

---

## ✨ Features

- **Plain-language input** — Describe your project in plain English; no design jargon required.
- **Visual color swatches** — Hex codes are rendered as clickable, copyable color swatches directly in the browser.
- **Multiple export formats** — Copy the brief as Markdown, plain text, or JSON for use in any design workflow.
- **Pydantic-validated output** — GPT-4o responses are parsed and validated so every required field is always present.
- **Stateless & instant** — No database, no accounts. Generate, copy, and go — deployable anywhere in minutes.

---

## 🚀 Quick Start

**1. Clone and install**

```bash
git clone https://github.com/your-org/brief_forge.git
cd brief_forge
pip install -e .
```

**2. Configure environment**

```bash
cp .env.example .env
# Open .env and add your OpenAI API key
```

**3. Run the app**

```bash
flask --app brief_forge run --debug
```

Open [http://localhost:5000](http://localhost:5000) in your browser, describe your design idea, and hit **Generate**.

---

## 📖 Usage Examples

### Web UI

Type a plain-language description into the input field:

```
A landing page for a mindfulness app targeting busy professionals.
Calm, modern feel. Should feel trustworthy but approachable.
```

Brief Forge returns a fully structured design brief with:
- Suggested layout and grid structure
- Color palette with named swatches and hex codes
- Typography pairings (display + body fonts)
- Copy hierarchy (headline, subhead, CTA)
- Mood descriptors

### API

You can also call the `/generate` endpoint directly:

```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{"description": "A landing page for a mindfulness app targeting busy professionals."}'
```

**Response (abbreviated):**

```json
{
  "brief": {
    "title": "Mindfulness App Landing Page",
    "mood": ["calm", "trustworthy", "modern", "approachable"],
    "color_palette": {
      "swatches": [
        { "name": "Soft Sage", "hex": "#A8B5A2", "usage": "Primary background" },
        { "name": "Deep Navy", "hex": "#1E2D40", "usage": "Headlines and CTAs" },
        { "name": "Warm Cream", "hex": "#F5F0E8", "usage": "Section alternates" }
      ]
    },
    "typography": {
      "display": "Playfair Display",
      "body": "Inter",
      "pairing_note": "Elegant serif headline with clean sans-serif body text."
    },
    "layout": {
      "grid": "12-column",
      "description": "Full-width hero with centered content, alternating two-column feature rows."
    },
    "copy_hierarchy": {
      "headline": "Find Your Calm. Even on Your Busiest Day.",
      "subheadline": "Guided sessions built for professionals with no time to spare.",
      "cta": "Start Free Today"
    }
  },
  "formats": {
    "markdown": "...",
    "text": "...",
    "json": "..."
  }
}
```

### Re-format an existing brief

```bash
curl -X POST http://localhost:5000/format \
  -H "Content-Type: application/json" \
  -d '{"brief": { ...brief object... }, "format": "markdown"}'
```

---

## 🗂 Project Structure

```
brief_forge/
├── brief_forge/
│   ├── __init__.py          # Package initializer; exposes create_app()
│   ├── app.py               # Flask app factory, routes, request handling
│   ├── generator.py         # OpenAI integration; prompt building & response parsing
│   ├── models.py            # Pydantic models: DesignBrief, ColorPalette, Typography, Layout
│   ├── formatter.py         # Renders briefs to Markdown, plain text, or JSON
│   ├── templates/
│   │   ├── index.html       # Main single-page UI with input form
│   │   └── brief_partial.html  # Jinja2 partial for structured brief display
│   └── static/
│       └── style.css        # Responsive stylesheet with color swatch rendering
├── tests/
│   ├── test_app.py          # Flask route integration tests
│   ├── test_generator.py    # Generator unit tests (mocked OpenAI)
│   ├── test_formatter.py    # Formatter output tests for all three formats
│   └── test_models.py       # Pydantic model validation and serialization tests
├── .env.example             # Environment variable template
├── pyproject.toml           # Project metadata and dependencies
└── README.md
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and set the following variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ Yes | — | Your OpenAI API key ([get one here](https://platform.openai.com/api-keys)) |
| `OPENAI_MODEL` | No | `gpt-4o` | Model used for brief generation. Use `gpt-4o-mini` for faster/cheaper output. |
| `OPENAI_MAX_TOKENS` | No | `2048` | Maximum tokens in the LLM response. |
| `OPENAI_TEMPERATURE` | No | `0.7` | Controls output creativity (0.0–1.0). |
| `FLASK_SECRET_KEY` | ✅ Yes | — | Secret key for Flask session security. |
| `FLASK_DEBUG` | No | `false` | Set to `true` to enable debug mode. |

**Example `.env`:**

```dotenv
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o
FLASK_SECRET_KEY=your-random-secret-key
FLASK_DEBUG=false
```

---

## 🧪 Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

All tests are fully mocked — no OpenAI API key required to run the test suite.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

*Built with [Jitter](https://github.com/jitter-ai) — an AI agent that ships code daily.*
