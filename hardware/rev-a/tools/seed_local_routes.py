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


def require_net(items, name: str):
    if any(item.GetNetname() != name for item in items):
        actual = [item.GetNetname() for item in items]
        raise SystemExit(f"{name} endpoints changed: {actual}")
    return items[0].GetNetCode()


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
    sig1 = board.GetLayerID("In2.Cu")
    sig3 = board.GetLayerID("In4.Cu")
    sig4 = board.GetLayerID("In5.Cu")

    # 5V_VCC: local via-in-pad bridge for the small U6 input pad.
    first = get_pad(board, "C40", "1")
    second = get_pad(board, "U6", "1")
    code = require_net([first, second], "5V_VCC")
    add_via(board, first.GetPosition(), code)
    add_via(board, second.GetPosition(), code)
    add_track(board, first.GetPosition(), second.GetPosition(), sig3, 0.25, code)

    # BAT_CELL_NEG: compact protection-cluster star on SIG4.
    local = [
        get_pad(board, "U3", "4"),
        get_pad(board, "Q1", "1"),
        get_pad(board, "R62", "2"),
        get_pad(board, "C67", "2"),
    ]
    through = get_pad(board, "J3", "2")
    code = require_net(local + [through], "BAT_CELL_NEG")
    for item in local:
        add_via(board, item.GetPosition(), code)
    hub = pcbnew.VECTOR2I_MM(4.23, 64.50)
    for item in local:
        add_track(board, item.GetPosition(), hub, sig4, 0.30, code)
    add_track(board, hub, through.GetPosition(), sig4, 0.30, code)

    # BAT_RAW: the bottom-side test point cannot be escaped with the 0.5 mm
    # class width.  Connect it to the through-hole battery connector on SIG1.
    testpoint = get_pad(board, "TP35", "1")
    battery = get_pad(board, "J3", "1")
    code = require_net([testpoint, battery], "BAT_RAW")
    add_via(board, testpoint.GetPosition(), code)
    add_track(board, testpoint.GetPosition(), battery.GetPosition(), sig1, 0.30, code)

    # PMID: short top-side neck-down between charger IC and its local capacitor.
    pmid_cap = get_pad(board, "C28", "1")
    pmid_ic = get_pad(board, "U2", "23")
    code = require_net([pmid_cap, pmid_ic], "PMID")
    add_track(board, pmid_cap.GetPosition(), pmid_ic.GetPosition(), pcbnew.F_Cu, 0.25, code)

    # SYS_SWITCHED: escape the small U20 output pad to the nearby bulk capacitor
    # on SIG4 before the 0.5 mm trunk autoroute is attempted.
    switched_ic = get_pad(board, "U20", "6")
    switched_cap = get_pad(board, "C3", "1")
    code = require_net([switched_ic, switched_cap], "SYS_SWITCHED")
    add_via(board, switched_ic.GetPosition(), code)
    add_via(board, switched_cap.GetPosition(), code)
    add_track(board, switched_ic.GetPosition(), switched_cap.GetPosition(), sig4, 0.30, code)

    # SYS_SWITCHED_5V: tie the three adjacent U6 output pads together with a
    # legal 0.20 mm neck-down and join them to the local output capacitor.
    output_cap = get_pad(board, "C50", "1")
    output_pads = [
        get_pad(board, "U6", "14"),
        get_pad(board, "U6", "15"),
        get_pad(board, "U6", "16"),
    ]
    code = require_net([output_cap] + output_pads, "SYS_SWITCHED_5V")
    add_track(board, output_cap.GetPosition(), output_pads[2].GetPosition(), pcbnew.F_Cu, 0.25, code)
    add_track(board, output_pads[2].GetPosition(), output_pads[1].GetPosition(), pcbnew.F_Cu, 0.20, code)
    add_track(board, output_pads[1].GetPosition(), output_pads[0].GetPosition(), pcbnew.F_Cu, 0.20, code)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output), board)
    print(f"SEEDED_BOARD={args.output}")
    print("SEEDED_NETS=5V_VCC,BAT_CELL_NEG,BAT_RAW,PMID,SYS_SWITCHED,SYS_SWITCHED_5V")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
