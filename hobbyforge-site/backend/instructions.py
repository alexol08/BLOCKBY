from __future__ import annotations

from typing import Any


def make_diagram(title: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], callouts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "type": "assembly",
        "title": title,
        "nodes": nodes,
        "edges": edges,
        "callouts": callouts or [],
    }


def simple_step_diagram(page_number: int, title: str, parts: list[str]) -> dict[str, Any]:
    safe_parts = [str(part) for part in parts if str(part).strip()][:3]
    if page_number == 1:
        return make_diagram(
            "Prepare and verify the kit",
            [
                {"id": "workspace", "label": "Workspace", "x": 36, "y": 112},
                {"id": "parts", "label": "Sorted parts", "x": 166, "y": 112},
                {"id": "bom", "label": "Verified BOM", "x": 296, "y": 112},
            ],
            [
                {"from": "workspace", "to": "parts", "label": "sort"},
                {"from": "parts", "to": "bom", "label": "tick off"},
            ],
            [{"text": "Do not order unverified items", "x": 90, "y": 54}],
        )
    if page_number == 2:
        return make_diagram(
            "Prototype the core function",
            [
                {"id": "input", "label": safe_parts[0] if safe_parts else "Input", "x": 36, "y": 112},
                {"id": "controller", "label": safe_parts[1] if len(safe_parts) > 1 else "Controller", "x": 166, "y": 112},
                {"id": "output", "label": safe_parts[2] if len(safe_parts) > 2 else "Output", "x": 296, "y": 112},
            ],
            [
                {"from": "input", "to": "controller", "label": "signal"},
                {"from": "controller", "to": "output", "label": "control"},
            ],
            [{"text": "Use reversible connections first", "x": 92, "y": 54}],
        )
    if page_number == 3:
        return make_diagram(
            "Fit and mount the build",
            [
                {"id": "model", "label": "CAD/model", "x": 48, "y": 78},
                {"id": "mount", "label": "Mounting", "x": 178, "y": 78},
                {"id": "assembly", "label": "Assembly", "x": 178, "y": 166},
            ],
            [
                {"from": "model", "to": "mount", "label": "measure"},
                {"from": "mount", "to": "assembly", "label": "fasten"},
            ],
            [{"text": "Check fit before permanent assembly", "x": 76, "y": 44}],
        )
    return make_diagram(
        title,
        [
            {"id": "test", "label": "Test", "x": 44, "y": 112},
            {"id": "photo", "label": "Document", "x": 170, "y": 112},
            {"id": "publish", "label": "Publish", "x": 296, "y": 112},
        ],
        [
            {"from": "test", "to": "photo", "label": "record"},
            {"from": "photo", "to": "publish", "label": "share"},
        ],
        [{"text": "Update notes after every fix", "x": 104, "y": 54}],
    )


def fallback_instruction_book(profile: dict[str, Any], brief: dict[str, Any], sourcing: dict[str, Any]) -> dict[str, Any]:
    project_name = brief.get("projectName") or brief.get("title") or "Hobby project"
    items = [item for item in sourcing.get("items", []) if item.get("required", True)]
    part_names = [item.get("name", "Part") for item in items][:8]

    pages = [
        {
            "pageNumber": 1,
            "title": "Lay out the kit",
            "purpose": "Confirm that the build is ready before doing anything permanent.",
            "partsNeeded": part_names[:5] or ["Verified BOM", "workspace", "labels"],
            "actions": [
                "Clear a workspace and put the project brief nearby.",
                "Sort parts into labelled groups.",
                "Tick off every required part against the verified source cards.",
            ],
            "checks": [
                "No required items are missing.",
                "Every orderable item has a verified source candidate.",
                "Owned items are still checked for compatibility.",
            ],
            "animationCue": "parts-fan-in",
            "helpPrompt": "I am missing a part or a source card is unverified.",
            "diagram": simple_step_diagram(1, "Lay out the kit", part_names),
        },
        {
            "pageNumber": 2,
            "title": "Prototype the core function",
            "purpose": "Test the most important assumption with reversible connections or temporary materials.",
            "partsNeeded": part_names[:6] or ["core parts", "temporary fixtures"],
            "actions": [
                "Build the smallest version that can prove the idea.",
                "Avoid permanent glue, solder, or cutting until the test passes.",
                "Write down any part substitutions or fit problems.",
            ],
            "checks": [
                "The core function works at least once.",
                "Nothing overheats, binds, cracks, or behaves unexpectedly.",
                "The design can still be safely changed.",
            ],
            "animationCue": "prototype-pulse",
            "helpPrompt": "My prototype does not work or behaves differently than expected.",
            "diagram": simple_step_diagram(2, "Prototype the core function", part_names),
        },
        {
            "pageNumber": 3,
            "title": "Fit, mount, and tidy",
            "purpose": "Turn the prototype into a repeatable assembly.",
            "partsNeeded": part_names[:8] or ["prototype", "mounts", "fasteners"],
            "actions": [
                "Measure final fit before cutting, printing, or fastening.",
                "Use removable fasteners where possible.",
                "Route wires or joints so the build is easy to inspect.",
            ],
            "checks": [
                "Parts are secure but serviceable.",
                "No blocked ventilation, unstable loads, pinched wires, or sharp edges.",
                "The final build matches the project brief.",
            ],
            "animationCue": "assembly-stack",
            "helpPrompt": "Something does not fit or I need to change the model.",
            "diagram": simple_step_diagram(3, "Fit and mount", part_names),
        },
        {
            "pageNumber": 4,
            "title": "Test and publish",
            "purpose": "Make the project safe, repeatable, and easy for others to understand.",
            "partsNeeded": ["finished build", "photos", "notes"],
            "actions": [
                "Run the final test checklist twice.",
                "Photograph important assembly points.",
                "Publish the brief, verified BOM, instruction pages, and known limitations.",
            ],
            "checks": [
                "Instructions match the final build.",
                "Known compatibility issues are documented.",
                "The project page does not include unverified source claims.",
            ],
            "animationCue": "book-complete",
            "helpPrompt": "Help me write a clear public project page.",
            "diagram": simple_step_diagram(4, "Test and publish", part_names),
        },
    ]

    return {
        "safe": True,
        "title": f"{project_name} instruction book",
        "intro": "A LEGO-style build guide with structured SVG diagrams, checks, and help prompts.",
        "safetyBeforeStart": [
            "Use age-appropriate supervision for tools, heat, electricity, cutting, dust, fumes, or moving parts.",
            "Stop if anything overheats, smells unusual, cracks, shorts, becomes unstable, or behaves unpredictably.",
            "Follow manufacturer instructions for real tools and components.",
        ],
        "pages": pages,
        "testPlan": [
            "Test the smallest safe prototype first.",
            "Change one variable at a time when debugging.",
            "Record failures and update the published project notes.",
        ],
        "troubleshooting": [
            "Compare the build to the compatibility checklist.",
            "Check dimensions, orientation, source-card notes, and selected parts.",
            "Use the help tool with the page number and exact symptom.",
        ],
        "helpPrompts": [page["helpPrompt"] for page in pages],
    }


def fallback_help(question: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "safe": True,
        "diagnosis": "Start with the simplest reversible check and avoid changing multiple things at once.",
        "nextChecks": [
            "Confirm the instruction page number and the exact part involved.",
            "Check orientation, dimensions, voltage/current ratings if relevant, and selected source notes.",
            "Compare against the last known working state.",
        ],
        "likelyCauses": [
            "Missing or substituted part",
            "Unverified source or wrong variant",
            "Mismatched dimension, connector, footprint, or orientation",
            "Skipped check step",
        ],
        "recommendedAction": f"Document the symptom, undo the last reversible change if possible, and test one change at a time. Your note: {question[:180]}",
        "whenToStop": "Stop and ask a trusted adult or qualified person if there is heat, unusual smell, cracking, instability, or electrical uncertainty.",
    }
