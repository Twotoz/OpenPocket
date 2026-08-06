#!/usr/bin/env python3
"""Complete the three local power escapes left by the clean power autoroute."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import pcbnew


def footprint(board: pcbnew.BOARD, reference: str) -> pcbnew.FOOTPRINT:
    for item in board.GetFootprints():
        if item.GetReference() == reference:
            return item
    raise KeyError(reference)


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    for item in footprint(board, reference).Pads():
        if item.GetNumber() == number:
            return item
    raise KeyError(f"{reference}.{number}")


def add_track(board, start, end, layer, width_mm, net_code):
    item = pcbnew.PCB_TRACK(board)
    item.SetStart(start)
    item.SetEnd(end)
    item.SetLayer(layer)
    item.SetWidth(pcbnew.FromMM(width_mm))
    item.SetNetCode(net_code)
    item.SetLocked(True)
    board.Add(item)


def add_via(board, position, net_code, diameter_mm=0.40, drill_mm=0.20):
    item = pcbnew.PCB_VIA(board)
    item.SetPosition(position)
    item.SetWidth(pcbnew.FromMM(diameter_mm))
    item.SetDrill(pcbnew.FromMM(drill_mm))
    item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    item.SetNetCode(net_code)
    item.SetLocked(True)
    board.Add(item)


def track_endpoints(board, net_name: str, layer: int | None = None):
    result = []
    for item in board.GetTracks():
        if isinstance(item, pcbnew.PCB_VIA):
            continue
        if item.GetNetname() != net_name:
            continue
        if layer is not None and item.GetLayer() != layer:
            continue
        result.extend((item.GetStart(), item.GetEnd()))
    return result


def nearest(points, target):
    return min(points, key=lambda point: math.hypot(point.x-target.x, point.y-target.y))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input))
    sig3 = board.GetLayerID("In4.Cu")

    # 5V_VCC: the class-wide router cannot leave U6.1.  Small via-in-pad
    # escapes on the two local endpoints connect them directly on SIG3.
    u6_1 = pad(board, "U6", "1")
    c40_1 = pad(board, "C40", "1")
    if u6_1.GetNetname() != "5V_VCC" or c40_1.GetNetname() != "5V_VCC":
        raise SystemExit("5V_VCC endpoints changed")
    code = u6_1.GetNetCode()
    add_via(board, u6_1.GetPosition(), code)
    add_via(board, c40_1.GetPosition(), code)
    add_track(board, u6_1.GetPosition(), c40_1.GetPosition(), sig3, 0.20, code)

    # BAT_CELL_NEG: join the already routed protection cluster to J3.2.
    j3_2 = pad(board, "J3", "2")
    if j3_2.GetNetname() != "BAT_CELL_NEG":
        raise SystemExit("BAT_CELL_NEG endpoint changed")
    points = track_endpoints(board, "BAT_CELL_NEG", pcbnew.F_Cu)
    source = nearest(points, j3_2.GetPosition())
    add_track(board, source, j3_2.GetPosition(), pcbnew.F_Cu, 0.25, j3_2.GetNetCode())

    # SYS_SWITCHED_5V: the three adjacent U6 output pads form one F.Cu island.
    # Drop U6.16 to SIG3 and join the nearest routed SIG3 endpoint.
    u6_16 = pad(board, "U6", "16")
    if u6_16.GetNetname() != "SYS_SWITCHED_5V":
        raise SystemExit("SYS_SWITCHED_5V endpoint changed")
    points = track_endpoints(board, "SYS_SWITCHED_5V", sig3)
    destination = nearest(points, u6_16.GetPosition())
    add_via(board, u6_16.GetPosition(), u6_16.GetNetCode())
    add_track(board, u6_16.GetPosition(), destination, sig3, 0.20, u6_16.GetNetCode())

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output), board)
    print(f"COMPLETED_POWER_BOARD={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
