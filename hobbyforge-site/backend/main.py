from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.ai import (
    BUILD_HELP_PROMPT,
    HELP_SCHEMA,
    INSTRUCTION_BOOK_PROMPT,
    INSTRUCTION_SCHEMA,
    PROJECT_BRIEF_SCHEMA,
    PROJECT_PLANNER_PROMPT,
    SOURCING_PLAN_SCHEMA,
    SOURCING_PROMPT,
    call_openai_json,
)
from backend.instructions import fallback_help, fallback_instruction_book
from backend.models import (
    HelpRequest,
    InstructionsRequest,
    OrderRequest,
    Profile,
    ProjectRefineRequest,
    SaveProjectRequest,
    SourcingRequest,
    make_id,
    now_iso,
)
from backend.safety import evaluate_action_safety, evaluate_project_safety
from backend.sourcing import fallback_sourcing_plan, validate_checkout_items, verify_sourcing_plan
from backend.store import read_store, write_store

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
load_dotenv(ROOT / ".env")

app = FastAPI(title="Blockyby API", version="0.2.0")


def compact_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def list_from_any(value: Any, limit: int = 40) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[,\n;•]+", str(value or ""))
    return [compact_whitespace(item) for item in raw if compact_whitespace(item)][:limit]


def dump_model(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return value
    return {}


def normalize_profile(profile: Profile | dict[str, Any] | None) -> dict[str, Any]:
    raw = dump_model(profile)
    return {
        "id": raw.get("id") or make_id("profile"),
        "name": compact_whitespace(raw.get("name") or "Local hobbyist"),
        "skills": list_from_any(raw.get("skills")),
        "tools": list_from_any(raw.get("tools")),
        "materials": list_from_any(raw.get("materials")),
        "stock": list_from_any(raw.get("stock")),
        "shippingAddress": compact_whitespace(raw.get("shippingAddress") or ""),
        "notes": compact_whitespace(raw.get("notes") or ""),
        "updatedAt": now_iso(),
    }


def budget_label(score: int | float | str) -> str:
    try:
        n = float(score)
    except (TypeError, ValueError):
        n = 50
    if n < 30:
        return "cheap-first"
    if n > 70:
        return "best-quality"
    return "balanced"


def fallback_project_brief(request: ProjectRefineRequest) -> dict[str, Any]:
    profile = normalize_profile(request.profile)
    safety = evaluate_project_safety(request.idea, profile, [dump_model(m) for m in request.messages])
    if not safety.safe:
        return {
            "safe": False,
            "reply": safety.message,
            "projectName": "Safer project needed",
            "summary": "The submitted idea was blocked by the safety gate.",
            "feasibilityScore": 0,
            "costStrategy": "blocked",
            "coreRequirements": [],
            "assumptions": [],
            "questions": ["Can you reframe this as a safe educational, decorative, robotics, art, or garden-sensor project?"],
            "riskFlags": safety.matches,
            "compatibilityChecklist": [],
            "projectBriefMarkdown": f"# Safer project needed\n\n{safety.message}",
            "safety": safety.to_dict(),
        }

    idea = compact_whitespace(request.idea) or "Custom hobby project"
    label = budget_label(request.budgetQuality)
    idea_lc = idea.lower()
    is_electronics = any(word in idea_lc for word in ["sensor", "monitor", "arduino", "esp", "raspberry", "led", "robot", "pcb", "circuit", "schematic", "controller"])
    is_making = any(word in idea_lc for word in ["3d", "cad", "enclosure", "print", "mount", "bracket", "case", "model"])
    is_wood = any(word in idea_lc for word in ["wood", "shelf", "desk", "table", "cabinet", "stand"])

    requirements: list[str] = []
    if is_electronics:
        requirements.extend(["Voltage/current compatibility", "Controller and library choice", "Safe low-voltage test plan"])
    if is_making:
        requirements.extend(["Dimensional sketch or CAD model", "Material and fastening plan", "Fit-check prototype"])
    if is_wood:
        requirements.extend(["Cut list", "Fastener/joinery plan", "Surface finish and fit checks"])
    if not requirements:
        requirements.extend(["Clear outcome definition", "Verified BOM", "Step-by-step test checklist"])

    owned_skills = profile.get("skills", [])[:5]
    assumptions = [
        f"Optimisation mode is {label}.",
        "Already-owned tools and materials should be reused where compatible.",
        f"Known skills: {', '.join(owned_skills)}." if owned_skills else "Beginner-friendly path with explanations included.",
    ]

    return {
        "safe": True,
        "reply": "This looks feasible as a safe hobby build. Next, verify parts and generate a source-backed BOM before writing instructions.",
        "projectName": idea[:56],
        "summary": f"A guided build plan for: {idea}.",
        "feasibilityScore": 0.74,
        "costStrategy": label,
        "coreRequirements": requirements,
        "assumptions": assumptions,
        "questions": [
            "What size or performance target should the first version meet?",
            "Which tools or materials do you not want to buy?",
            "Should the demo focus on a quick prototype or a polished final build?",
        ],
        "riskFlags": [
            "Check heat, power, sharp edges, moving parts, dust/fumes, stability, and age-appropriate supervision where relevant."
        ],
        "compatibilityChecklist": [
            "Match dimensions, connectors, footprints, voltage/current ratings, materials, and software-library versions.",
            "Do not order until source cards show a verified candidate for each required item.",
            "Use schematic block diagrams first, then raw views only when debugging exact file coordinates.",
        ],
        "projectBriefMarkdown": f"# {idea}\n\n## Strategy\n- " + "\n- ".join(assumptions) + "\n\n## Requirements\n- " + "\n- ".join(requirements),
    }


def profile_import_fallback(source_type: str, url: str, text: str) -> dict[str, Any]:
    text_lc = text.lower()
    skill_hints = ["soldering", "arduino", "raspberry pi", "python", "javascript", "cad", "3d printing", "woodworking", "electronics", "pcb", "robotics"]
    tool_hints = ["soldering iron", "multimeter", "oscilloscope", "3d printer", "laser cutter", "drill", "breadboard", "bench supply", "calipers"]
    material_hints = ["pla", "petg", "wood", "filament", "resistors", "capacitors", "led", "wire", "acrylic", "screws"]
    extracted = normalize_profile(
        {
            "name": "Imported hobbyist",
            "skills": [hint for hint in skill_hints if hint in text_lc],
            "tools": [hint for hint in tool_hints if hint in text_lc],
            "materials": [hint for hint in material_hints if hint in text_lc],
            "stock": [hint for hint in material_hints if hint in text_lc],
            "notes": f"Parsed locally from {source_type}. Review before saving.",
        }
    )
    return {
        "sourceType": source_type,
        "sourceUrl": url,
        "confidence": 0.58 if len(text) > 80 else 0.25,
        "extracted": extracted,
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "backend": "python-fastapi",
        "aiEnabled": bool(os.getenv("OPENAI_API_KEY")),
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "fallbackModel": os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4o-mini"),
        "time": now_iso(),
    }


@app.post("/api/ai/test")
def ai_test(body: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = {
        "name": "ai_connection_test",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["ok", "message"],
            "properties": {"ok": {"type": "boolean"}, "message": {"type": "string"}},
        },
    }
    try:
        result = call_openai_json(
            instructions="Return a tiny JSON status object for the Blockyby AI connection test.",
            input_data={"ping": compact_whitespace((body or {}).get("ping", "test"))},
            schema=schema,
        )
        if result is None:
            return {"ok": True, "aiEnabled": False, "result": {"ok": True, "message": "No API key set. Local fallback mode is active."}}
        return {"ok": True, "aiEnabled": True, "result": result}
    except Exception as exc:
        return {
            "ok": False,
            "aiEnabled": bool(os.getenv("OPENAI_API_KEY")),
            "error": str(exc),
            "hint": "Check OPENAI_API_KEY, OPENAI_MODEL, billing/model access, and network access. Local fallbacks keep the app usable.",
        }


@app.post("/api/profile")
def save_profile(profile: Profile) -> dict[str, Any]:
    clean = normalize_profile(profile)
    store = read_store()
    existing = [p for p in store.get("profiles", []) if p.get("id") != clean["id"]]
    store["profiles"] = [clean] + existing[:19]
    write_store(store)
    return {"profile": clean}


@app.post("/api/profile/import")
def import_profile(body: dict[str, Any]) -> dict[str, Any]:
    source_type = compact_whitespace(body.get("sourceType") or "CV/pasted text")
    url = compact_whitespace(body.get("url") or "")
    text = compact_whitespace(body.get("text") or "")[:20000]
    return profile_import_fallback(source_type, url, text)


@app.post("/api/project/refine")
def refine_project(request: ProjectRefineRequest) -> dict[str, Any]:
    safety = evaluate_project_safety(request.idea, normalize_profile(request.profile), [dump_model(m) for m in request.messages])
    if not safety.safe:
        return fallback_project_brief(request)

    input_data = {
        "idea": request.idea,
        "profile": normalize_profile(request.profile),
        "conversation": [dump_model(m) for m in request.messages][-10:],
        "budgetQuality": request.budgetQuality,
        "ownedOptimisation": request.ownedOptimisation,
    }
    try:
        result = call_openai_json(instructions=PROJECT_PLANNER_PROMPT, input_data=input_data, schema=PROJECT_BRIEF_SCHEMA)
        return result or fallback_project_brief(request)
    except Exception as exc:
        result = fallback_project_brief(request)
        result["_aiError"] = str(exc)
        return result


@app.post("/api/sourcing")
def create_sourcing(request: SourcingRequest) -> dict[str, Any]:
    profile = normalize_profile(request.profile)
    safety = evaluate_action_safety("source", request.idea, request.brief, profile)
    if not safety.safe:
        return {
            "safe": False,
            "summary": safety.message,
            "estimatedTotal": 0,
            "currency": "EUR",
            "items": [],
            "existingAssets": [],
            "compatibilityNotes": [],
            "sourcingDifficulty": "blocked",
            "orderWarnings": safety.matches,
            "safety": safety.to_dict(),
        }
    input_data = {
        "profile": profile,
        "brief": request.brief,
        "idea": request.idea,
        "budgetQuality": request.budgetQuality,
        "guardrails": [
            "Draft only safe hobby items.",
            "Do not invent supplier prices; the backend verifier owns source-card pricing.",
            "Mark already-owned materials as owned when profile evidence supports it.",
        ],
    }
    try:
        draft = call_openai_json(instructions=SOURCING_PROMPT, input_data=input_data, schema=SOURCING_PLAN_SCHEMA)
        if draft and draft.get("safe", True):
            return verify_sourcing_plan(draft)
        if draft and not draft.get("safe", True):
            draft["estimatedTotal"] = 0
            draft["items"] = []
            return draft
        return fallback_sourcing_plan(profile, request.brief, request.idea, request.budgetQuality)
    except Exception as exc:
        result = fallback_sourcing_plan(profile, request.brief, request.idea, request.budgetQuality)
        result["_aiError"] = str(exc)
        return result


@app.post("/api/instructions")
def create_instructions(request: InstructionsRequest) -> dict[str, Any]:
    safety = evaluate_action_safety("instruct", request.profile, request.brief, request.sourcing)
    if not safety.safe:
        return {
            "safe": False,
            "title": "Safer project needed",
            "intro": safety.message,
            "safetyBeforeStart": ["Choose a safe non-hazardous project."],
            "pages": [],
            "testPlan": [],
            "troubleshooting": [],
            "helpPrompts": [],
            "safety": safety.to_dict(),
        }

    input_data = {"profile": request.profile, "brief": request.brief, "sourcing": request.sourcing}
    try:
        result = call_openai_json(instructions=INSTRUCTION_BOOK_PROMPT, input_data=input_data, schema=INSTRUCTION_SCHEMA)
        return result or fallback_instruction_book(request.profile, request.brief, request.sourcing)
    except Exception as exc:
        result = fallback_instruction_book(request.profile, request.brief, request.sourcing)
        result["_aiError"] = str(exc)
        return result


@app.post("/api/help")
def help_with_build(request: HelpRequest) -> dict[str, Any]:
    safety = evaluate_action_safety("help", request.question, request.context)
    if not safety.safe:
        return {
            "safe": False,
            "diagnosis": safety.message,
            "nextChecks": [],
            "likelyCauses": [],
            "recommendedAction": "Choose a safe non-hazardous project or ask about a safe part of the workflow.",
            "whenToStop": "Stop if the project involves unsafe or restricted materials.",
            "safety": safety.to_dict(),
        }
    try:
        result = call_openai_json(
            instructions=BUILD_HELP_PROMPT,
            input_data={"question": request.question, "context": request.context},
            schema=HELP_SCHEMA,
        )
        return result or fallback_help(request.question, request.context)
    except Exception as exc:
        result = fallback_help(request.question, request.context)
        result["_aiError"] = str(exc)
        return result


@app.get("/api/projects")
def get_projects() -> dict[str, Any]:
    store = read_store()
    return {"projects": store.get("projects", [])}


@app.post("/api/projects")
def save_project(request: SaveProjectRequest) -> dict[str, Any]:
    project = {
        "id": request.id or make_id("project"),
        "title": compact_whitespace(request.title or request.brief.get("projectName") or "Untitled project"),
        "brief": request.brief,
        "sourcing": verify_sourcing_plan(request.sourcing) if request.sourcing else {},
        "instructions": request.instructions,
        "visibility": "public" if request.visibility == "public" else "private",
        "createdAt": request.createdAt or now_iso(),
        "updatedAt": now_iso(),
    }
    safety = evaluate_action_safety("save", project)
    if not safety.safe:
        raise HTTPException(status_code=400, detail={"error": safety.message, "matches": safety.matches})
    store = read_store()
    existing = [p for p in store.get("projects", []) if p.get("id") != project["id"]]
    store["projects"] = [project] + existing[:99]
    write_store(store)
    return {"project": project}


def selected_source_total(item: dict[str, Any]) -> float:
    selected_index = int(item.get("selectedSourceIndex", -1))
    candidates = item.get("sourceCandidates") or []
    if selected_index < 0 or selected_index >= len(candidates):
        return 0.0
    source = candidates[selected_index]
    if source.get("priceConfidence") != "exact":
        return 0.0
    unit_total = float(source.get("totalPriceEstimate") or source.get("unitPrice") or 0)
    return round(unit_total * float(item.get("quantity", 1) or 1), 2)


@app.post("/api/order")
def create_order(request: OrderRequest) -> dict[str, Any]:
    items = [item for item in request.items if item.get("selected", True) and item.get("orderable") and item.get("sourceStatus") != "owned"]
    safety = evaluate_action_safety("order", items)
    if not safety.safe:
        raise HTTPException(status_code=400, detail={"error": safety.message, "matches": safety.matches})

    ok, problems = validate_checkout_items(items)
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "Cart needs verification before checkout.", "problems": problems})

    total = round(sum(selected_source_total(item) for item in items), 2)
    order = {
        "id": f"order_{uuid4().hex[:12]}",
        "status": "mock_checkout_created",
        "message": "Mock order created from verified source-card prices. This demo does not place a real supplier/payment order.",
        "itemCount": len(items),
        "estimatedTotal": total,
        "currency": request.currency,
        "createdAt": now_iso(),
    }
    store = read_store()
    store["orders"] = [order] + store.get("orders", [])[:99]
    write_store(store)
    return {"order": order}


# Keep this last so /api routes are matched before static files.
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
