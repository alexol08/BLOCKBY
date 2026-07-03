from __future__ import annotations

import json
import os
from typing import Any


PROJECT_PLANNER_PROMPT = """
You are Blockyby's safe project-planning agent for hobbyists.
Validate feasibility, ask useful clarifying questions, and optimise around owned tools/materials plus a cheap-to-best quality slider.
Prefer reversible prototypes, low-risk materials, clear compatibility checks, and beginner-readable language.
Do not help with unsafe, illegal, restricted, or age-restricted projects. Return only the provided JSON schema.
""".strip()


SOURCING_PROMPT = """
You are Blockyby's BOM drafting agent.
Draft a practical bill of materials for a safe hobby build, but do not invent supplier prices, stock, shipping, or checkout readiness.
Reuse already-owned profile items where compatible. Each suggested item must include compatibility notes and a short reason it belongs in the project.
The backend sourcing verifier will replace planning estimates with source-card data, so keep unitPriceEstimate as a rough planning estimate only.
Do not help source unsafe, illegal, restricted, or age-restricted items. Return only the provided JSON schema.
""".strip()


INSTRUCTION_BOOK_PROMPT = """
You are Blockyby's LEGO-style instruction book generator.
Create concise page-based build steps with SVG-friendly diagram JSON.
Focus on reversible prototyping, source verification, compatibility checks, test checkpoints, and safe stopping points.
Do not include hazardous or restricted instructions. Return only the provided JSON schema.
""".strip()


BUILD_HELP_PROMPT = """
You are Blockyby's instruction-book help assistant.
Answer the builder's question using the current instruction page, project brief, sourcing plan, and chat history.
Keep advice practical, step-by-step, reversible, and safe. Ask the user to stop and review when a part is missing, incompatible, overheats, smells unusual, or behaves unpredictably.
Do not give hazardous or restricted instructions. Return only the provided JSON schema.
""".strip()


def _extract_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None) or getattr(content, "output_text", None)
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks)


def _parse_loose_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise ValueError("Model returned no text output")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def model_candidates() -> list[str]:
    values = [
        os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4o-mini"),
        "gpt-4.1-mini",
        "gpt-4o-mini",
    ]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def call_openai_json(*, instructions: str, input_data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any] | None:
    """Return parsed JSON from OpenAI, or None when no key is configured.

    All application routes have deterministic local fallbacks, so missing keys,
    account limits, or network problems should not stop the demo from running.
    """

    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError("The openai package is not installed. Run: pip install -r requirements.txt") from exc

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45")))
    errors: list[str] = []

    for model in model_candidates():
        try:
            response = client.responses.create(
                model=model,
                instructions=instructions,
                input=json.dumps(input_data, ensure_ascii=False),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema["name"],
                        "strict": True,
                        "schema": schema["schema"],
                    }
                },
            )
            parsed = _parse_loose_json(_extract_output_text(response))
            parsed["_modelUsed"] = model
            parsed["_aiProvider"] = "openai"
            return parsed
        except Exception as exc:  # pragma: no cover - network/model/account dependent
            errors.append(f"{model}: {exc}")

    raise RuntimeError("OpenAI request failed: " + " | ".join(errors[-4:]))


PROJECT_BRIEF_SCHEMA: dict[str, Any] = {
    "name": "project_brief",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "safe",
            "reply",
            "projectName",
            "summary",
            "feasibilityScore",
            "costStrategy",
            "coreRequirements",
            "assumptions",
            "questions",
            "riskFlags",
            "compatibilityChecklist",
            "projectBriefMarkdown",
        ],
        "properties": {
            "safe": {"type": "boolean"},
            "reply": {"type": "string"},
            "projectName": {"type": "string"},
            "summary": {"type": "string"},
            "feasibilityScore": {"type": "number"},
            "costStrategy": {"type": "string"},
            "coreRequirements": {"type": "array", "items": {"type": "string"}},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "questions": {"type": "array", "items": {"type": "string"}},
            "riskFlags": {"type": "array", "items": {"type": "string"}},
            "compatibilityChecklist": {"type": "array", "items": {"type": "string"}},
            "projectBriefMarkdown": {"type": "string"},
        },
    },
}


SOURCING_PLAN_SCHEMA: dict[str, Any] = {
    "name": "sourcing_plan_draft",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "safe",
            "summary",
            "estimatedTotal",
            "currency",
            "items",
            "existingAssets",
            "compatibilityNotes",
            "sourcingDifficulty",
            "orderWarnings",
        ],
        "properties": {
            "safe": {"type": "boolean"},
            "summary": {"type": "string"},
            "estimatedTotal": {"type": "number"},
            "currency": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "id", "name", "category", "required", "quantity", "unitPriceEstimate", "vendorHint",
                        "ownedAlternative", "compatibilityNotes", "difficulty", "safetyNotes", "sourceStatus",
                        "orderable", "selected"
                    ],
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "category": {"type": "string"},
                        "required": {"type": "boolean"},
                        "quantity": {"type": "number"},
                        "unitPriceEstimate": {"type": "number"},
                        "vendorHint": {"type": "string"},
                        "ownedAlternative": {"type": "string"},
                        "compatibilityNotes": {"type": "string"},
                        "difficulty": {"type": "string"},
                        "safetyNotes": {"type": "string"},
                        "sourceStatus": {"type": "string"},
                        "orderable": {"type": "boolean"},
                        "selected": {"type": "boolean"},
                    },
                },
            },
            "existingAssets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "type", "licenseHint", "description", "sourceHint", "viewAction"],
                    "properties": {
                        "title": {"type": "string"},
                        "type": {"type": "string"},
                        "licenseHint": {"type": "string"},
                        "description": {"type": "string"},
                        "sourceHint": {"type": "string"},
                        "viewAction": {"type": "string"},
                    },
                },
            },
            "compatibilityNotes": {"type": "array", "items": {"type": "string"}},
            "sourcingDifficulty": {"type": "string"},
            "orderWarnings": {"type": "array", "items": {"type": "string"}},
        },
    },
}


INSTRUCTION_SCHEMA: dict[str, Any] = {
    "name": "instruction_book",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["safe", "title", "intro", "safetyBeforeStart", "pages", "testPlan", "troubleshooting", "helpPrompts"],
        "properties": {
            "safe": {"type": "boolean"},
            "title": {"type": "string"},
            "intro": {"type": "string"},
            "safetyBeforeStart": {"type": "array", "items": {"type": "string"}},
            "pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "pageNumber", "title", "purpose", "partsNeeded", "actions", "checks", "animationCue", "helpPrompt", "diagram"
                    ],
                    "properties": {
                        "pageNumber": {"type": "number"},
                        "title": {"type": "string"},
                        "purpose": {"type": "string"},
                        "partsNeeded": {"type": "array", "items": {"type": "string"}},
                        "actions": {"type": "array", "items": {"type": "string"}},
                        "checks": {"type": "array", "items": {"type": "string"}},
                        "animationCue": {"type": "string"},
                        "helpPrompt": {"type": "string"},
                        "diagram": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["type", "title", "nodes", "edges", "callouts"],
                            "properties": {
                                "type": {"type": "string"},
                                "title": {"type": "string"},
                                "nodes": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["id", "label", "x", "y"],
                                        "properties": {
                                            "id": {"type": "string"},
                                            "label": {"type": "string"},
                                            "x": {"type": "number"},
                                            "y": {"type": "number"},
                                        },
                                    },
                                },
                                "edges": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["from", "to", "label"],
                                        "properties": {
                                            "from": {"type": "string"},
                                            "to": {"type": "string"},
                                            "label": {"type": "string"},
                                        },
                                    },
                                },
                                "callouts": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["text", "x", "y"],
                                        "properties": {
                                            "text": {"type": "string"},
                                            "x": {"type": "number"},
                                            "y": {"type": "number"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "testPlan": {"type": "array", "items": {"type": "string"}},
            "troubleshooting": {"type": "array", "items": {"type": "string"}},
            "helpPrompts": {"type": "array", "items": {"type": "string"}},
        },
    },
}


HELP_SCHEMA: dict[str, Any] = {
    "name": "build_help",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["safe", "diagnosis", "nextChecks", "likelyCauses", "recommendedAction", "whenToStop"],
        "properties": {
            "safe": {"type": "boolean"},
            "diagnosis": {"type": "string"},
            "nextChecks": {"type": "array", "items": {"type": "string"}},
            "likelyCauses": {"type": "array", "items": {"type": "string"}},
            "recommendedAction": {"type": "string"},
            "whenToStop": {"type": "string"},
        },
    },
}
