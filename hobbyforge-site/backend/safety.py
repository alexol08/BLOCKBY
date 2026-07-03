from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

RESTRICTED_PROJECT_KEYWORDS = [
    "weapon", "firearm", "explosive", "hazardous chemical", "toxin",
    "controlled substance", "drug", "nicotine", "gambling", "adult",
    "self harm", "dangerous challenge",
]

STRICT_ACTIONS = {"source", "instruct", "order"}


@dataclass
class SafetyResult:
    safe: bool
    action: str
    severity: Literal["none", "review", "blocked"]
    matches: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "action": self.action,
            "severity": self.severity,
            "matches": self.matches,
            "message": self.message,
        }


def _to_searchable_text(*parts: Any) -> str:
    chunks = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, str):
            chunks.append(part)
        else:
            try:
                chunks.append(json.dumps(part, default=str))
            except TypeError:
                chunks.append(str(part))
    return " ".join(chunks).lower()


def evaluate_action_safety(action: str, *parts: Any) -> SafetyResult:
    text = _to_searchable_text(*parts)
    matches = sorted({word for word in RESTRICTED_PROJECT_KEYWORDS if word in text})

    if not matches:
        return SafetyResult(
            safe=True,
            action=action,
            severity="none",
            matches=[],
            message="No restricted sourcing issue detected.",
        )

    blocked = action in STRICT_ACTIONS
    return SafetyResult(
        safe=False,
        action=action,
        severity="blocked" if blocked else "review",
        matches=matches[:8],
        message=(
            "This project may involve restricted or hazardous materials. "
            "Blockyby will not source parts, place orders, or generate build steps for it. "
            "Try a safe educational, decorative, robotics, art, garden sensor, or organisation project instead."
        ),
    )
