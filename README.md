# Blockyby

Blockyby is an AI-assisted hobby project platform that helps makers plan, source, simulate, build, and publish projects from one place.

The app is designed for hobbyists who want to turn an idea into a complete build plan. A user can define their skills, tools, materials, stock, and project goals, then use the AI discussion flow to refine the idea, generate a bill of materials, produce guided instructions, and preview supported CAD/EDA assets.

> Current app folder: `hobbyforge-site`

---

## Features

- **Hobbyist profile setup**
  - Add skills, tools, materials, stock, and notes.
  - Optionally add shipping details for future ordering workflows.
  - Import profile-style text or CV-style information with review before saving.

- **AI project discussion**
  - Discuss and refine a project idea with an LLM-backed planning flow.
  - Generate structured project briefs.
  - Optimise project decisions using a cheap-to-best quality slider.
  - Reuse already-owned tools and materials where possible.

- **Sourcing and BOM planning**
  - Generate a bill of materials.
  - Detect possible owned alternatives.
  - Add compatibility notes and sourcing difficulty.
  - Keep checkout mocked until real supplier/payment integrations are added.

- **Instruction book generation**
  - Create LEGO-style step-by-step project instructions.
  - Include checks, safety notes, and troubleshooting prompts.
  - Use the build helper when stuck.

- **Simulation Lab**
  - Preview `.stl` files.
  - Inspect `.sch` / `.kicad_sch` schematic files.
  - View `.kicad_pcb` / `.pcb` board files.
  - Export a simple PCB-to-STL board model.
  - Extend the simulation system with custom modules.

- **Hosted project library**
  - Save generated projects locally.
  - Mark projects as public/private.
  - Use generated briefs, BOMs, and instructions as publishable project pages.

---

## Tech Stack

- **Runtime:** Node.js
- **Server:** Native Node HTTP server
- **Frontend:** HTML, CSS, JavaScript
- **AI:** OpenAI Responses API-compatible server route
- **Storage:** Local JSON file store
- **Simulation:** Browser-based CAD/EDA preview modules

No framework is required for the current version.

---

## Repository Structure

```text
blockyby/
├── README.md
├── LICENSE
└── hobbyforge-site/
    ├── server.mjs
    ├── package.json
    ├── public/
    │   ├── index.html
    │   ├── app.js
    │   ├── styles.css
    │   ├── samples/
    │   └── sim/
    ├── scripts/
    │   └── smoke.mjs
    └── data/
        └── store.json
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/BasilAmin/blockyby.git
cd blockyby/hobbyforge-site
```

### 2. Install Node.js

The app requires Node.js 18 or newer.

On Fedora:

```bash
sudo dnf install nodejs
```

Check your versions:

```bash
node -v
npm -v
```

### 3. Create your `.env` file

Create a `.env` file inside `hobbyforge-site`:

```bash
nano .env
```

Add:

```env
PORT=5179

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_FALLBACK_MODEL=gpt-4o-mini

OPENAI_TIMEOUT_MS=45000
```

The app can run without `OPENAI_API_KEY`, but it will use local mock responses instead of real AI responses.

### 4. Start the app

```bash
npm start
```

Open:

```text
http://localhost:5179
```

### 5. Run the smoke test

```bash
npm test
```

---

## Using the App

1. Open the local site.
2. Fill in the hobbyist profile with your skills, tools, stock, and materials.
3. Go to the project discussion area.
4. Describe the project you want to build.
5. Adjust the cheap-to-best slider.
6. Generate a project brief.
7. Generate sourcing/BOM suggestions.
8. Generate the instruction book.
9. Use Simulation Lab to load supported CAD/EDA files.
10. Save or publish the project locally.

---

## Simulation Lab

The Simulation Lab currently supports lightweight preview and inspection for:

```text
.stl
.sch
.kicad_sch
.kicad_pcb
.pcb
```

Sample files are included in:

```text
hobbyforge-site/public/samples/
```

To test rendering:

1. Start the app.
2. Open Simulation Lab.
3. Choose **Load asset**.
4. Select one of the sample files.

### PCB to CAD

The app includes a basic PCB-to-STL export path. This is intended as a starting point, not a production-grade mechanical CAD export.

Future improvements could include:

- KiCad parser improvements
- STEP export
- GLTF export
- 3D component models
- WebGL or Three.js rendering
- SPICE-style schematic simulation
- ERC/DRC checks

---

## OpenAI API Notes

The OpenAI key is loaded server-side from `.env`.

Do not put your API key in frontend files.

The app includes:

- `/api/health`
- `/api/ai/test`
- AI routes for project discussion, sourcing, instructions, and help
- local fallback responses when no API key is configured

After changing `.env`, restart the server:

```bash
npm start
```

Then use the **Test API** button in the app sidebar.

---

## Safety Notes

Blockyby is designed for safe hobby projects.

The starter includes a safety gate that blocks restricted or hazardous projects before sourcing or instruction generation. Keep this protection enabled if the app is used by younger users, public users, or school/community groups.

The app should not be used to generate instructions or sourcing workflows for dangerous, illegal, or age-restricted projects.

---

## Roadmap

- [ ] Real supplier integrations
- [ ] Reviewed cart and checkout flow
- [ ] User accounts
- [ ] Cloud project hosting
- [ ] Rich public project pages
- [ ] WebGL CAD viewer
- [ ] Better STL/STEP/GLTF support
- [ ] KiCad-native PCB parsing
- [ ] Schematic simulation
- [ ] Component compatibility agent
- [ ] Community remix/fork system
- [ ] Project comments and build logs
- [ ] Image uploads for troubleshooting

---

## Development

Start the local server:

```bash
npm start
```

Run tests:

```bash
npm test
```

The app intentionally uses a simple Node/HTML/CSS/JS stack so it is easy to inspect, modify, and extend.

---

## License

This project is licensed under the MIT License.
