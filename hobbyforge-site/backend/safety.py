from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

# Keep this plain and readable for hackathon debugging.
# This does not replace a production Trust & Safety system: it is a keyword
# gate meant to catch obviously unsafe hobby-project requests before the app
# will source parts, place a mock order, or generate build instructions.
# Broaden this list rather than narrow it if you find gaps during testing.
RESTRICTED_PROJECT_KEYWORDS = [
    # Weapons / explosives
    "weapon", "firearm", "gun", "pistol", "rifle", "shotgun", "ammo",
    "ammunition", "explosive", "bomb", "grenade", "detonator",
    "blasting cap", "black powder", "gunpowder", "silencer", "suppressor",
    "taser", "stun gun", "pepper spray", "throwing knife", "brass knuckles",
    "molotov",
    # Hazardous chemicals / toxins
    "hazardous chemical", "toxin", "poison", "nerve agent", "chlorine gas",
    "thermite", "radioactive",
    # Drugs / controlled substances
    "controlled substance", "narcotic", "methamphetamine", "fentanyl",
    "drug", "nicotine", "vape juice",
    # Other restricted categories
    "gambling", "adult content", "self harm", "suicide method",
    "dangerous challenge", "surveillance without consent",
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
    chunks: list[str] = []
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


def evaluate_project_safety(*parts: Any) -> SafetyResult:
    return evaluate_action_safety("plan", *parts)
