#!/usr/bin/env python3
"""Export a Specctra DSN while protecting the two ground-reference planes."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


REV = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path,
                        default=REV / "openpocket-rev-a.kicad_pcb")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board))
    if board.GetCopperLayerCount() != 8:
        raise SystemExit("expected the reviewed eight-layer board")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.ExportSpecctraDSN(board, str(args.output)):
        raise SystemExit("KiCad failed to export Specctra DSN")
    text = args.output.read_text(encoding="utf-8")
    for name in ("GND1", "GND2"):
        old = f"(layer {name}\n      (type signal)"
        new = f"(layer {name}\n      (type power)"
        if text.count(old) != 1:
            raise SystemExit(f"cannot protect {name} in exported DSN")
        text = text.replace(old, new, 1)
    args.output.write_text(text, encoding="utf-8")
    print(f"EXPORTED_DSN={args.output}")
    print("PROTECTED_PLANES=GND1,GND2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
