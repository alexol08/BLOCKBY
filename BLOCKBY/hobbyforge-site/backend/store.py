from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STORE_FILE = ROOT / "data" / "store.json"
DEFAULT_STORE = {"profiles": [], "projects": [], "orders": []}


def ensure_store() -> None:
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_FILE.exists():
        STORE_FILE.write_text(json.dumps(DEFAULT_STORE, indent=2), encoding="utf-8")


def read_store() -> dict[str, Any]:
    ensure_store()
    try:
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        broken = STORE_FILE.with_suffix(".broken.json")
        STORE_FILE.replace(broken)
        STORE_FILE.write_text(json.dumps(DEFAULT_STORE, indent=2), encoding="utf-8")
        return DEFAULT_STORE.copy()


def write_store(store: dict[str, Any]) -> None:
    ensure_store()
    tmp = STORE_FILE.with_suffix(f".{STORE_FILE.name}.tmp")
    tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE_FILE)
