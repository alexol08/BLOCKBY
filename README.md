# Blockyby Python Hackathon Site

This is a hackathon-ready rebuild of the Blockyby / HobbyForge idea with a **Python FastAPI backend** and a simple browser frontend.

The goal is to make the project easier to understand and debug while still keeping the parts that must run in the browser as JavaScript.

## What this version includes

- Python backend for project planning, sourcing verification, instruction generation, safety checks, local storage, and mock checkout.
- Warm cream / beige / woody UI theme.
- Verified source cards for BOM items.
- Mock supplier catalogue with supplier name, product description, part numbers, stock, price, and evidence notes.
- Checkout readiness checks so unverified items cannot be ordered in the demo flow.
- LEGO-style instruction book with generated SVG diagrams.
- Simulation Lab with:
  - schematic block diagram mode by default
  - raw schematic mode for debugging
  - PCB viewer
  - PCB-to-STL export
  - lightweight STL viewer
- Built-in sample files.
- Smoke test script.
- No frontend framework, so your team can read the code directly.

## Folder map

```text
hobbyforge-site/
├── backend/
│   ├── main.py          # API routes
│   ├── models.py        # request/data models
│   ├── store.py         # data/store.json read/write helpers
│   ├── safety.py        # safety checks
│   ├── sourcing.py      # BOM generation and source verification
│   ├── instructions.py  # instruction book and diagram data
│   └── ai.py            # optional OpenAI structured-output helper
├── public/
│   ├── index.html       # page structure
│   ├── styles.css       # warm woody theme
│   ├── app.js           # UI, buttons, API calls, rendering
│   ├── sim.js           # schematic / PCB / STL browser viewer
│   └── samples/         # demo files
├── data/
│   └── store.json       # created automatically
├── scripts/
│   └── smoke.py         # static checks
├── requirements.txt
├── package.json         # optional npm convenience scripts
└── .env.example
```

## Run on Fedora

```bash
cd hobbyforge-site
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn backend.main:app --reload --port 5179
```

Open:

```text
http://localhost:5179
```

You can also use the npm shortcuts if you want:

```bash
npm start
npm test
```

The actual backend is still Python.

## Optional OpenAI setup

The app works without an API key. It uses local fallback agents.

To enable real AI calls, edit `.env`:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_FALLBACK_MODEL=gpt-4o-mini
```

Restart the server after editing `.env`.

Then use the **Test API** button in the sidebar.

## How the app works

```text
Browser UI
  public/index.html
  public/styles.css
  public/app.js
  public/sim.js
        ↓ fetch('/api/...')
Python backend
  backend/main.py
        ↓
Business logic
  safety.py
  sourcing.py
  instructions.py
  ai.py
        ↓
Local JSON storage
  data/store.json
```

## What to improve next

### 1. Schematic spaghetti

The default schematic view now uses block diagrams instead of raw wire coordinates. Improve this by building a better netlist parser and grouping blocks by actual connected nets.

Start in:

```text
public/sim.js
```

Look for:

```js
parseSchematic()
renderSchematicBlock()
renderSchematicRaw()
```

### 2. Sourcing verification

The source cards currently use a demo catalogue. Replace this with real supplier adapters later.

Start in:

```text
backend/sourcing.py
```

Look for:

```python
MOCK_CATALOGUE
find_source_candidates()
verify_sourcing_plan()
validate_checkout_items()
```

### 3. Instruction diagrams

Instruction diagrams are generated as JSON and rendered as SVG. This is easier to debug than generating image files.

Backend data starts in:

```text
backend/instructions.py
```

Frontend rendering starts in:

```text
public/app.js
```

Look for:

```js
renderDiagram()
renderInstructions()
```

### 4. UI theme

The warm theme is mostly CSS variables.

Start in:

```text
public/styles.css
```

Look for:

```css
:root
```

### 5. Ordering and safety

The app creates mock orders only. This is intentional for the hackathon. It refuses checkout if source verification is incomplete.

Start in:

```text
backend/main.py
backend/sourcing.py
backend/safety.py
public/app.js
```

Look for:

```python
create_order()
validate_checkout_items()
evaluate_action_safety()
```

and:

```js
canCheckout()
createMockOrder()
```

## Smoke test

```bash
python scripts/smoke.py
```

This checks that core files exist and Python backend files compile. If the server is running, it also checks `/api/health`.

## Notes

This is not production checkout, not production EDA simulation, and not production CAD export. It is meant to be readable, editable, and demo-friendly.
