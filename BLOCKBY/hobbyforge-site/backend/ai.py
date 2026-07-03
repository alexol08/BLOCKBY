from __future__ import annotations

import json
import os
from typing import Any


def _extract_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    chunks = []
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
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def call_openai_json(*, instructions: str, input_data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any] | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("The openai package is not installed. Run: pip install -r requirements.txt") from exc

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45")))
    errors = []

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
        except Exception as exc:
            errors.append(f"{model}: {exc}")

    raise RuntimeError("OpenAI request failed: " + " | ".join(errors[-4:]))


PROJECT_BRIEF_SCHEMA = {
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


INSTRUCTION_SCHEMA = {
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
