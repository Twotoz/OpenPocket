#!/usr/bin/env python3
"""Build an autoroute-feasibility placement from the reviewed Rev-A PCB.

This is deliberately a test harness, not a production-layout generator.
Mechanical connectors remain fixed. Major electrical blocks are moved to a
connectivity-oriented floorplan, small parts follow their most likely owner,
and the project's own ground-fanout implementation is then reapplied.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys

import pcbnew


BOARD_W = 115.0
BOARD_H = 72.0
GND_NAMES = {"", "GND", "NC"}

FIXED_REFS = {
    "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9",
    "J11", "J12", "J13",
    "FID1", "FID2", "FID3", "FID4", "FID5", "FID6",
}

# Corrected for the *actual committed board*: J1 is fixed at (29.75, 26.00).
# Coordinates are desired centres; the legalizer may nudge a part locally.
PROPOSED = {
    "U1": (70.0, 25.0),
    "U2": (16.0, 60.0),
    "U3": (3.0, 58.0),
    "Q1": (7.0, 62.0),
    "U4": (25.0, 59.0),
    "U20": (31.0, 61.0),
    "U5": (54.0, 54.0),
    "U6": (67.0, 52.0),
    "U7": (46.0, 52.0),
    "U8": (80.0, 49.0),
    "U9": (99.0, 58.0),
    "U10": (86.0, 44.0),
    "MOD1": (16.0, 40.0),
    "U11": (35.0, 51.0),
    "U12": (53.0, 47.0),
    "U13": (58.0, 43.0),
    "U14": (35.0, 38.0),
    "U15": (48.0, 33.0),
    "U16": (55.0, 35.0),
    "U17": (18.0, 34.0),
    "U18": (45.0, 62.0),
    "U19": (74.0, 62.0),
    "U21": (92.0, 25.0),
    "U22": (90.0, 19.0),
    "BZ1": (89.0, 35.0),
    "Q2": (84.0, 39.0),
    "D2": (87.0, 39.0),
    "ESD1": (60.0, 12.0),
    "ESD2": (98.0, 18.0),
    "ESD3": (102.0, 18.0),
    "ESD4": (105.0, 65.0),
    "F1": (52.0, 11.0),
    "TVS1": (55.0, 11.0),
    "JP1": (31.0, 43.0),
    "Y1": (36.0, 57.0),
    "Y2": (45.0, 42.0),
    "L1": (20.0, 63.0),
    "L2": (58.0, 57.0),
    "L3": (73.0, 55.0),
    "L4": (12.0, 34.0),
    "L5": (90.0, 48.0),
    "D1": (12.0, 39.0),
    "FB1": (41.0, 51.0),
    "FB2": (45.0, 46.0),
    "FB3": (48.0, 46.0),
    "FB4": (39.0, 32.0),
}

OWNER_ANCHORS = {
    *(f"U{i}" for i in range(1, 23)),
    "MOD1", "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8",
    "J9", "J11", "J12", "J13", "BZ1",
}

CRITICAL_PREFIXES = (
    "LCD_", "USB_", "SD_", "VRX_", "OSD_", "AMT_", "RX_", "BL_",
    "CHG_", "L3V3_", "L5V_", "AUDIO_", "SPK", "CRSF_",
)

# Keep the broad RGB escape between the fixed FFC and U14 free of components.
KEEP_OUTS = {
    "F": [(18.0, 29.0, 45.0, 32.5)],
    "B": [(18.0, 29.0, 45.0, 32.5)],
}


def pos_mm(fp: pcbnew.FOOTPRINT) -> tuple[float, float]:
    p = fp.GetPosition()
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


def pad_nets(fp: pcbnew.FOOTPRINT) -> set[str]:
    return {
        pad.GetNetname()
        for pad in fp.Pads()
        if pad.GetNetname() not in GND_NAMES
    }


def has_pth(fp: pcbnew.FOOTPRINT) -> bool:
    return any(
        pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        for pad in fp.Pads()
    )


def side_keys(fp: pcbnew.FOOTPRINT) -> tuple[str, ...]:
    if has_pth(fp):
        return ("F", "B")
    return ("B",) if fp.GetLayer() == pcbnew.B_Cu else ("F",)


def fp_box_mm(fp: pcbnew.FOOTPRINT, side: str, margin_mm: float = 0.20) -> tuple[float, float, float, float]:
    layer = pcbnew.B_CrtYd if side == "B" else pcbnew.F_CrtYd
    courtyard = fp.GetCourtyard(layer)
    merged = None
    for pad in fp.Pads():
        pb = pad.GetBoundingBox()
        if merged is None:
            merged = pcbnew.BOX2I(pb.GetOrigin(), pb.GetSize())
        else:
            merged.Merge(pb)
    if merged is None:
        bb = fp.GetBoundingBox()
        merged = pcbnew.BOX2I(bb.GetOrigin(), bb.GetSize())
    if not courtyard.IsEmpty():
        merged.Merge(courtyard.BBox())
    merged = merged.GetInflated(pcbnew.FromMM(margin_mm))
    return (
        pcbnew.ToMM(merged.GetLeft()),
        pcbnew.ToMM(merged.GetTop()),
        pcbnew.ToMM(merged.GetRight()),
        pcbnew.ToMM(merged.GetBottom()),
    )


def intersects(a: tuple[float, float, float, float],
               b: tuple[float, float, float, float]) -> bool:
    return not (
        a[2] <= b[0] or b[2] <= a[0] or
        a[3] <= b[1] or b[3] <= a[1]
    )


def in_bounds(bb: tuple[float, float, float, float]) -> bool:
    return bb[0] >= 0.8 and bb[1] >= 0.8 and bb[2] <= BOARD_W - 0.8 and bb[3] <= BOARD_H - 0.8


def candidate_offsets(max_radius: float, step: float = 0.5):
    yield (0.0, 0.0)
    rings = int(max_radius / step)
    for ring in range(1, rings + 1):
        r = ring * step
        for index in range(-ring, ring + 1):
            v = index * step
            yield (v, -r)
            yield (v, r)
            yield (-r, v)
            yield (r, v)


def legal_place(
    fp: pcbnew.FOOTPRINT,
    desired: tuple[float, float],
    occupied: dict[str, list[tuple[float, float, float, float]]],
    max_radius: float,
) -> tuple[float, float]:
    for dx, dy in candidate_offsets(max_radius):
        x, y = desired[0] + dx, desired[1] + dy
        fp.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        boxes = [(side, fp_box_mm(fp, side)) for side in side_keys(fp)]
        if any(not in_bounds(bb) for _, bb in boxes):
            continue
        blocked = False
        for side, bb in boxes:
            if any(intersects(bb, other) for other in occupied[side]):
                blocked = True
                break
            if any(intersects(bb, ko) for ko in KEEP_OUTS[side]):
                blocked = True
                break
        if blocked:
            continue
        for side, bb in boxes:
            occupied[side].append(bb)
        return x, y
    raise RuntimeError(
        f"{fp.GetReference()}: no legal placement within {max_radius:.1f} mm "
        f"of {desired[0]:.1f},{desired[1]:.1f}"
    )


def owner_for(
    ref: str,
    old_pos: dict[str, tuple[float, float]],
    nets: dict[str, set[str]],
    anchor_refs: set[str],
) -> str:
    own_nets = nets[ref]
    if not own_nets:
        return min(anchor_refs, key=lambda a: math.dist(old_pos[ref], old_pos[a]))

    net_counts: dict[str, int] = {}
    for anchor in anchor_refs:
        for net in nets[anchor]:
            net_counts[net] = net_counts.get(net, 0) + 1

    best: tuple[float, str] | None = None
    for anchor in anchor_refs:
        shared = own_nets & nets[anchor]
        if not shared:
            continue
        score = 0.0
        for net in shared:
            count = max(1, net_counts.get(net, 1))
            weight = 8.0 if count == 1 else 4.0 / count
            if net.startswith(CRITICAL_PREFIXES):
                weight *= 1.8
            score += weight
        distance = math.dist(old_pos[ref], old_pos[anchor])
        score += 2.0 / (1.0 + distance / 8.0)
        candidate = (score, anchor)
        if best is None or candidate > best:
            best = candidate
    if best is not None:
        return best[1]
    return min(anchor_refs, key=lambda a: math.dist(old_pos[ref], old_pos[a]))


def import_ground_fanout(generator_path: Path):
    spec = importlib.util.spec_from_file_location("openpocket_generate_design", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {generator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=("u14_90", "u14_270"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input))
    if board.GetCopperLayerCount() != 8:
        raise SystemExit("expected eight copper layers")

    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    missing = sorted((FIXED_REFS | set(PROPOSED)) - set(footprints))
    missing_required = sorted(set(PROPOSED) - set(footprints))
    if missing_required:
        raise SystemExit(f"missing required footprints: {missing_required}")

    fixed = {ref for ref in FIXED_REFS if ref in footprints}
    old_pos = {ref: pos_mm(fp) for ref, fp in footprints.items()}
    old_orientation = {ref: fp.GetOrientationDegrees() for ref, fp in footprints.items()}
    nets = {ref: pad_nets(fp) for ref, fp in footprints.items()}

    fixed_before = {
        ref: {
            "x": old_pos[ref][0],
            "y": old_pos[ref][1],
            "rotation": old_orientation[ref],
            "flipped": footprints[ref].IsFlipped(),
        }
        for ref in fixed
    }

    for item in list(board.GetTracks()):
        board.Remove(item)

    occupied: dict[str, list[tuple[float, float, float, float]]] = {
        "F": list(KEEP_OUTS["F"]),
        "B": list(KEEP_OUTS["B"]),
    }
    for ref in fixed:
        fp = footprints[ref]
        for side in side_keys(fp):
            occupied[side].append(fp_box_mm(fp, side))

    rotation = 90.0 if args.variant == "u14_90" else 270.0
    footprints["U14"].SetOrientationDegrees(rotation)

    proposed_refs = set(PROPOSED)
    proposed_order = sorted(
        proposed_refs,
        key=lambda ref: -sum(
            max(0.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
            for side in side_keys(footprints[ref])
            for bb in [fp_box_mm(footprints[ref], side, 0.0)]
        ),
    )
    actual: dict[str, tuple[float, float]] = {}
    for ref in proposed_order:
        actual[ref] = legal_place(
            footprints[ref], PROPOSED[ref], occupied, max_radius=8.0
        )

    anchor_refs = {
        ref for ref in OWNER_ANCHORS
        if ref in footprints and (ref in fixed or ref in proposed_refs)
    }
    anchor_new = {
        ref: (actual[ref] if ref in actual else old_pos[ref])
        for ref in anchor_refs
    }

    movable_small = [
        ref for ref in footprints
        if ref not in fixed and ref not in proposed_refs
    ]

    desired_small: dict[str, tuple[float, float]] = {}
    owners: dict[str, str] = {}
    for ref in movable_small:
        owner = owner_for(ref, old_pos, nets, anchor_refs)
        owners[ref] = owner
        ox, oy = old_pos[owner]
        dx = old_pos[ref][0] - ox
        dy = old_pos[ref][1] - oy
        length = math.hypot(dx, dy)
        cap = 7.0 if ref.startswith("TP") else 4.5
        if length > cap and length > 0:
            scale = cap / length
            dx *= scale
            dy *= scale
        nx, ny = anchor_new[owner]
        desired_small[ref] = (nx + dx, ny + dy)

    small_order = sorted(
        movable_small,
        key=lambda ref: (
            ref.startswith("TP"),
            -sum(
                max(0.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
                for side in side_keys(footprints[ref])
                for bb in [fp_box_mm(footprints[ref], side, 0.0)]
            ),
            ref,
        ),
    )
    for ref in small_order:
        actual[ref] = legal_place(
            footprints[ref], desired_small[ref], occupied, max_radius=15.0
        )

    generator = import_ground_fanout(
        Path(__file__).resolve().parent / "generate_design.py"
    )
    net_objects = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            name = pad.GetNetname()
            if name and name not in net_objects:
                net_objects[name] = pad.GetNet()
    generator.configure_plane_connections(board)
    generator.add_ground_fanout(board, net_objects)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output), board)

    fixed_after = {
        ref: {
            "x": pos_mm(footprints[ref])[0],
            "y": pos_mm(footprints[ref])[1],
            "rotation": footprints[ref].GetOrientationDegrees(),
            "flipped": footprints[ref].IsFlipped(),
        }
        for ref in fixed
    }
    if fixed_after != fixed_before:
        raise RuntimeError("mechanically fixed footprint changed")

    report = {
        "variant": args.variant,
        "input": str(args.input),
        "output": str(args.output),
        "fixed_footprints": sorted(fixed),
        "missing_optional_fixed": missing,
        "u14_rotation": rotation,
        "positions": {
            ref: {
                "desired": list(PROPOSED[ref]) if ref in PROPOSED else list(desired_small[ref]),
                "actual": list(pos_mm(footprints[ref])),
                "owner": owners.get(ref),
                "side": "B" if footprints[ref].IsFlipped() else "F",
                "rotation": footprints[ref].GetOrientationDegrees(),
            }
            for ref in sorted(actual)
        },
        "track_items_after_ground_fanout": len(list(board.GetTracks())),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PLACEMENT_BOARD={args.output}")
    print(f"PLACEMENT_REPORT={args.report}")
    print(f"U14_ROTATION={rotation}")
    print(f"GROUND_FANOUT_ITEMS={report['track_items_after_ground_fanout']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
