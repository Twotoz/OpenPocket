#!/usr/bin/env python3
"""Refuse a Rev-A manufacturing release without reviewed evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "release-status.json"
REQUIRED_SOURCES = (
    ROOT / "openpocket-rev-a.kicad_pro",
    ROOT / "openpocket-rev-a.kicad_sch",
    ROOT / "openpocket-rev-a.kicad_pcb",
)


def main() -> int:
    data = json.loads(STATUS.read_text(encoding="utf-8"))
    errors: list[str] = []
    for blocker in data["blockers"]:
        if not blocker["resolved"]:
            errors.append(f"{blocker['id']}: {blocker['required_evidence']}")
    for source in REQUIRED_SOURCES:
        if not source.is_file():
            errors.append(f"MISSING_SOURCE: {source.name}")
    if not data.get("manufacturing_release_allowed", False):
        errors.append("RELEASE_FLAG: manufacturing_release_allowed is false")
    if errors:
        print("OPENPOCKET_REV_A_RELEASE=BLOCKED")
        for error in errors:
            print(f"BLOCKER={error}")
        return 2
    print("OPENPOCKET_REV_A_RELEASE=READY_FOR_ARTIFACT_GENERATION")
    return 0


if __name__ == "__main__":
    sys.exit(main())
