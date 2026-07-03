# Blockyby / HobbyForge Merged Site

This folder contains the working merged app.

It uses the Python FastAPI version as the stable base, keeps the improved Simulation Lab, and adds the BLOCKBY-style sourcing/UI/LLM pieces that fit cleanly into the existing backend.

## Merged highlights

- **Simulation retained and working:** schematic block view, raw schematic view, PCB viewer, simple PCB-to-STL export, STL viewer, and built-in sample assets.
- **Sourcing upgraded:** exact local source cards, source-card data versioning, supplier search/review links, optional web-search candidates, optional live-link probes, and mock checkout validation that refuses unverified or unknown-price selected sources.
- **LLM layer upgraded:** separate prompts and strict JSON schemas for project planning, sourcing draft generation, instruction-book generation, and build-help support.
- **UI upgraded:** BLOCKBY-style build help chatbot added under the instruction book, richer source cards, link/checkout status display, and localStorage reset for old sourcing data.
- **Fallback-first reliability:** every AI route has local fallback behavior, so the app runs without an OpenAI API key.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5179
```

Open:

```text
http://localhost:5179
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5179
```

## Optional OpenAI setup

The app runs without a key. To enable live model calls, set this in `.env` and restart:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_FALLBACK_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=45
```

## Optional sourcing setup

By default, sourcing uses exact local source cards plus supplier review links. Optional network checks are disabled for reliability:

```env
BLOCKYBY_WEB_SEARCH=0
BLOCKYBY_LIVE_LINK_CHECKS=0
BLOCKYBY_HTTP_TIMEOUT_SECONDS=2
BLOCKYBY_MAX_WEB_RESULTS_PER_ITEM=2
```

Enable them only when your environment allows outgoing web requests and you want extra review candidates.

## File map

```text
backend/
  main.py          API routes
  ai.py            OpenAI structured-output helper, prompts, schemas
  sourcing.py      BOM fallback, verification, exact source cards, supplier/search candidates
  instructions.py  local instruction-book and build-help fallbacks
  safety.py        safety gates for planning, sourcing, instructions, help, checkout
  models.py        request/data models
  store.py         local JSON store helpers
public/
  index.html       page structure and build-help panel
  app.js           UI logic, sourcing rendering, instruction/help chat flows
  sim.js           schematic / PCB / STL browser viewer
  styles.css       UI theme
  samples/         demo schematic, PCB, and STL assets
scripts/
  smoke.py         compile/static/health smoke checks
```

## Test

```bash
python scripts/smoke.py
```

## Known limits

Mock checkout is intentionally not a real order. Supplier links are review aids unless you add real supplier adapters. The Simulation Lab is a browser previewer, not production CAD/EDA tooling.
