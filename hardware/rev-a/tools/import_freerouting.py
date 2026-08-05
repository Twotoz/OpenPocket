#!/usr/bin/env python3
"""Import a Freerouting session while preserving mechanical PCB invariants."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pcbnew


REV = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = REV / "openpocket-rev-a.kicad_pcb"


def footprint_state(board: pcbnew.BOARD) -> dict[str, tuple[int, int, float, int]]:
    return {
        footprint.GetReference(): (
            footprint.GetPosition().x,
            footprint.GetPosition().y,
            footprint.GetOrientationDegrees(),
            footprint.GetLayer(),
        )
        for footprint in board.GetFootprints()
    }


def outline_state(board: pcbnew.BOARD) -> tuple[int, int, int, int]:
    bounds = board.GetBoardEdgesBoundingBox()
    return bounds.GetX(), bounds.GetY(), bounds.GetWidth(), bounds.GetHeight()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.session.is_file() or args.session.stat().st_size == 0:
        raise SystemExit(f"missing or empty SES: {args.session}")

    board = pcbnew.LoadBoard(str(args.board))
    before_footprints = footprint_state(board)
    before_outline = outline_state(board)
    before_layers = board.GetCopperLayerCount()
    imported = pcbnew.ImportSpecctraSES(board, str(args.session))
    if imported is False:
        raise SystemExit("KiCad rejected the Freerouting session")

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    if footprint_state(board) != before_footprints:
        raise SystemExit("SES import changed footprint placement")
    if outline_state(board) != before_outline:
        raise SystemExit("SES import changed the board outline")
    if board.GetCopperLayerCount() != before_layers:
        raise SystemExit("SES import changed the copper-layer count")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output), board)
    print(f"IMPORTED_SESSION={args.session}")
    print(f"OUTPUT_BOARD={args.output}")
    print(f"TRACK_ITEMS={len(list(board.GetTracks()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
