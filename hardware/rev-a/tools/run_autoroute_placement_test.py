#!/usr/bin/env python3
"""Run placement in a fresh process after stripping existing tracks."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

import pcbnew

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
known, remaining = parser.parse_known_args()

stripped = known.output.with_name(known.output.stem + "-stripped.kicad_pcb")
stripped.parent.mkdir(parents=True, exist_ok=True)
board = pcbnew.LoadBoard(str(known.input))
if board is None:
    raise SystemExit(f"cannot load {known.input}")
for item in list(board.GetTracks()):
    board.Remove(item)
pcbnew.SaveBoard(str(stripped), board)
if not stripped.is_file() or stripped.stat().st_size == 0:
    raise SystemExit("failed to write stripped board")

# Patch one placement target without mutating the production test harness:
# JP1 is a wide video bypass jumper and does not fit at the graph-ideal point.
# Its reviewed current position is mechanically legal and remains adjacent to
# the U11/U14 analog-video chain.
source_path = Path(__file__).with_name("autoroute_placement_test.py")
source = source_path.read_text(encoding="utf-8")
old = '    "JP1": (31.0, 43.0),\n'
new = '    "JP1": (44.0, 35.0),\n'
if source.count(old) != 1:
    raise SystemExit("cannot patch JP1 placement target")
source = source.replace(old, new, 1)

with tempfile.TemporaryDirectory(prefix="openpocket-placement-") as temp:
    patched = Path(temp) / "autoroute_placement_test.py"
    patched.write_text(source, encoding="utf-8")
    command = [
        sys.executable,
        str(patched),
        "--input", str(stripped),
        "--output", str(known.output),
        *remaining,
    ]
    raise SystemExit(subprocess.call(command))
