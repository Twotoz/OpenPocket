#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pcbnew


def get_pad(board, ref: str, number: str):
    for fp in board.GetFootprints():
        if fp.GetReference() != ref:
            continue
        for item in fp.Pads():
            if item.GetNumber() == number:
                return item
    raise KeyError(f"missing {ref}.{number}")


def add_track(board, start, end, layer, width_mm: float, net_code: int):
    item = pcbnew.PCB_TRACK(board)
    item.SetStart(start)
    item.SetEnd(end)
    item.SetLayer(layer)
    item.SetWidth(pcbnew.FromMM(width_mm))
    item.SetNetCode(net_code)
    item.SetLocked(True)
    board.Add(item)


def add_via(board, position, net_code: int):
    item = pcbnew.PCB_VIA(board)
    item.SetPosition(position)
    item.SetWidth(pcbnew.FromMM(0.45))
    item.SetDrill(pcbnew.FromMM(0.20))
    item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    item.SetNetCode(net_code)
    item.SetLocked(True)
    board.Add(item)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input))
    sig3 = board.GetLayerID("In4.Cu")
    sig4 = board.GetLayerID("In5.Cu")

    first = get_pad(board, "C40", "1")
    second = get_pad(board, "U6", "1")
    if first.GetNetname() != "5V_VCC" or second.GetNetname() != "5V_VCC":
        raise SystemExit("5V_VCC endpoints changed")
    code = first.GetNetCode()
    add_via(board, first.GetPosition(), code)
    add_via(board, second.GetPosition(), code)
    add_track(board, first.GetPosition(), second.GetPosition(), sig3, 0.25, code)

    local = [
        get_pad(board, "U3", "4"),
        get_pad(board, "Q1", "1"),
        get_pad(board, "R62", "2"),
        get_pad(board, "C67", "2"),
    ]
    through = get_pad(board, "J3", "2")
    if any(item.GetNetname() != "BAT_CELL_NEG" for item in local + [through]):
        raise SystemExit("BAT_CELL_NEG endpoints changed")
    code = through.GetNetCode()
    for item in local:
        add_via(board, item.GetPosition(), code)
    hub = pcbnew.VECTOR2I_MM(4.23, 64.50)
    for item in local:
        add_track(board, item.GetPosition(), hub, sig4, 0.30, code)
    add_track(board, hub, through.GetPosition(), sig4, 0.30, code)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output), board)
    print(f"SEEDED_BOARD={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
