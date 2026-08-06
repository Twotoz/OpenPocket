#!/usr/bin/env python3
"""Run placement in a fresh process after stripping existing tracks."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

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

# The actual placement harness now starts in a new interpreter.  This avoids
# KiCad 9 SWIG references that become invalid after removing hundreds of tracks.
command = [
    sys.executable,
    str(Path(__file__).with_name("autoroute_placement_test.py")),
    "--input", str(stripped),
    "--output", str(known.output),
    *remaining,
]
raise SystemExit(subprocess.call(command))
