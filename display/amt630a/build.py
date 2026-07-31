#!/usr/bin/env python3
"""Deterministic AMT630A build gate; no unlicensed firmware fallback."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
APPROVAL = ROOT / "redistribution-approval.json"
PANEL = ROOT.parents[1] / "hardware" / "rev-a" / "references" / "AT050TN33-V1.pdf"


def main() -> int:
    blockers: list[str] = []
    if not APPROVAL.is_file():
        blockers.append("AMT630A_REDISTRIBUTION_APPROVAL_MISSING")
    else:
        approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
        if not approval.get("commercial_redistribution_allowed", False):
            blockers.append("AMT630A_COMMERCIAL_REDISTRIBUTION_NOT_ALLOWED")
        if not approval.get("source_revision") or not approval.get("license"):
            blockers.append("AMT630A_PROVENANCE_INCOMPLETE")
    if not PANEL.is_file():
        blockers.append("AT050TN33_V1_DATASHEET_MISSING")
    if blockers:
        print(json.dumps({"build": "blocked", "blockers": blockers}, sort_keys=True))
        return 2
    print(json.dumps({
        "build": "blocked",
        "blockers": ["REVIEWED_SOURCE_AND_TOOLCHAIN_NOT_YET_ADDED"]
    }, sort_keys=True))
    return 2


if __name__ == "__main__":
    sys.exit(main())
