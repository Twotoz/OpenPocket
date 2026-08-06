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

# Patch test-only placement details without mutating the production harness.
source_path = Path(__file__).with_name("autoroute_placement_test.py").resolve()
generator_path = Path(__file__).with_name("generate_design.py").resolve()
source = source_path.read_text(encoding="utf-8")

# JP1 is a wide video bypass jumper and does not fit at the graph-ideal point.
# Its reviewed current position remains adjacent to the U11/U14 video chain.
old_jp1 = '    "JP1": (31.0, 43.0),\n'
new_jp1 = '    "JP1": (44.0, 35.0),\n'
if source.count(old_jp1) != 1:
    raise SystemExit("cannot patch JP1 placement target")
source = source.replace(old_jp1, new_jp1, 1)

# The copied script runs from /tmp, so make the generator import point back to
# the real repository instead of resolving relative to the temporary script.
old_generator = '        Path(__file__).resolve().parent / "generate_design.py"\n'
new_generator = f'        Path(r"{generator_path}")\n'
if source.count(old_generator) != 1:
    raise SystemExit("cannot patch generate_design.py path")
source = source.replace(old_generator, new_generator, 1)

# Do not pre-place hundreds of through-GND vias before signal routing. The
# production fanout algorithm can fail in a dense cluster and, even when it
# succeeds, consumes channels on every signal layer. Ground stitching is a
# post-route operation for this feasibility run.
old_fanout = f'''    generator = import_ground_fanout(
        Path(r"{generator_path}")
    )
    net_objects = {{}}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            name = pad.GetNetname()
            if name and name not in net_objects:
                net_objects[name] = pad.GetNet()
    generator.configure_plane_connections(board)
    generator.add_ground_fanout(board, net_objects)

'''
new_fanout = '''    # Ground fanout intentionally deferred until after signal routing.

'''
if source.count(old_fanout) != 1:
    raise SystemExit("cannot defer pre-route ground fanout")
source = source.replace(old_fanout, new_fanout, 1)

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
