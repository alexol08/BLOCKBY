from __future__ import annotations

import json
import py_compile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

required = [
    "backend/main.py",
    "backend/models.py",
    "backend/store.py",
    "backend/safety.py",
    "backend/sourcing.py",
    "backend/instructions.py",
    "backend/ai.py",
    "public/index.html",
    "public/styles.css",
    "public/app.js",
    "public/sim.js",
    "public/samples/demo.kicad_sch",
    "public/samples/demo.kicad_pcb",
    "public/samples/demo-cube.stl",
    "requirements.txt",
]

missing = [path for path in required if not (ROOT / path).exists()]
if missing:
    raise SystemExit("Missing required files: " + ", ".join(missing))

for py_file in (ROOT / "backend").glob("*.py"):
    py_compile.compile(str(py_file), doraise=True)

package_json = ROOT / "package.json"
if package_json.exists():
    json.loads(package_json.read_text(encoding="utf-8"))

print("Static smoke checks passed.")

try:
    with urlopen("http://127.0.0.1:5179/api/health", timeout=1.5) as response:
        data = json.loads(response.read().decode("utf-8"))
        print("Running server health:", data.get("ok"), data.get("backend"))
except URLError:
    print("Server not running; start with: python -m uvicorn backend.main:app --reload --port 5179")
except TimeoutError:
    print("Server health check timed out; static checks still passed.")
