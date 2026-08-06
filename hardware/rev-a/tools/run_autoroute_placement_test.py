#!/usr/bin/env python3
"""Run the placement harness with a KiCad-9 SWIG lifetime workaround."""
from __future__ import annotations

from pathlib import Path
import runpy
import sys
import tempfile

source_path = Path(__file__).with_name("autoroute_placement_test.py")
source = source_path.read_text(encoding="utf-8")
old = '''    for item in list(board.GetTracks()):
        board.Remove(item)

    occupied: dict[str, list[tuple[float, float, float, float]]] = {
'''
new = '''    for item in list(board.GetTracks()):
        board.Remove(item)

    # KiCad 9 SWIG can invalidate previously obtained FOOTPRINT/PAD proxies
    # after a large batch of board.Remove() calls.  Save and reload the stripped
    # board, then rebuild every footprint proxy before continuing.
    stripped = args.output.with_name(args.output.stem + "-stripped.kicad_pcb")
    stripped.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(stripped), board)
    board = pcbnew.LoadBoard(str(stripped))
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}

    occupied: dict[str, list[tuple[float, float, float, float]]] = {
'''
if source.count(old) != 1:
    raise SystemExit("cannot apply KiCad-9 SWIG lifetime workaround")
source = source.replace(old, new, 1)
with tempfile.TemporaryDirectory(prefix="openpocket-placement-") as temp:
    patched = Path(temp) / "autoroute_placement_test_patched.py"
    patched.write_text(source, encoding="utf-8")
    sys.path.insert(0, str(source_path.parent))
    runpy.run_path(str(patched), run_name="__main__")
