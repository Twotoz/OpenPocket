#!/usr/bin/env python3
"""Audit routing characteristics that KiCad DRC does not judge electrically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pcbnew


REV = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = REV / "openpocket-rev-a.kicad_pcb"

CRITICAL_GROUPS = {
    "usb": ("USB_D+", "USB_D-", "USB_D+_MCU", "USB_D-_MCU"),
    "rf": ("RX_RF",),
    "video": (
        "VRX_VIDEO_RAW", "VRX_VIDEO_COUPLED", "VRX_VIDEO_TO_OSD",
        "OSD_VIDEO_RAW", "OSD_VIDEO_BYP", "AMT_CVBS_PRE", "AMT_CVBS1",
    ),
    "crystal": ("OSD_XTAL_IN", "OSD_XTAL_OUT", "AMT_XTAL_IN", "AMT_XTAL_OUT"),
    "switch": ("CHG_SW", "DISP_SW", "L3V3_A", "L3V3_B", "L5V_SW", "BL_SW"),
    "clock": ("LCD_DCLK", "LCD_DCLK_SRC", "RX_CLK", "RX_CLK_MCU", "SD_CLK", "SD_CLK_MCU"),
    "high_current": (
        "VBUS_RAW", "VBUS_USB", "PMID", "BAT_RAW", "BAT_PROTECTED",
        "BAT_CELL_NEG", "SYS_ALWAYS", "SYS_SWITCHED", "SYS_SWITCHED_5V",
    ),
    "battery_sense": ("BAT_NEG_SENSE", "PACK_NEG_SENSE"),
}

MINIMUM_WIDTH_MM = {
    "usb": 0.15,
    "rf": 0.25,
    "video": 0.25,
    "crystal": 0.20,
    "switch": 0.80,
    "clock": 0.12,
    "high_current": 1.20,
    "battery_sense": 0.40,
}


def mm(value: int | float) -> float:
    return pcbnew.ToMM(value)


def audit(board_path: Path) -> tuple[dict[str, object], list[str]]:
    board = pcbnew.LoadBoard(str(board_path))
    tracks = list(board.GetTracks())
    pads = [pad for footprint in board.GetFootprints()
            for pad in footprint.Pads()]
    report: dict[str, object] = {
        "board": str(board_path),
        "copper_layers": board.GetCopperLayerCount(),
        "groups": {},
    }
    errors: list[str] = []

    gnd_layers = {board.GetLayerID(name) for name in ("GND1", "GND2")}
    illegal_gnd = sorted({
        item.GetNetname() for item in tracks
        if item.GetLayer() in gnd_layers and item.GetNetname() not in ("", "GND")
    })
    if illegal_gnd:
        errors.append(f"SIGNALS_ON_GND_LAYER: {illegal_gnd}")

    for group, nets in CRITICAL_GROUPS.items():
        group_rows: dict[str, object] = {}
        for net in nets:
            items = [item for item in tracks if item.GetNetname() == net]
            segments = [item for item in items if not isinstance(item, pcbnew.PCB_VIA)]
            vias = [item for item in items if isinstance(item, pcbnew.PCB_VIA)]
            widths = [mm(item.GetWidth()) for item in segments]
            layers = sorted({board.GetLayerName(item.GetLayer()) for item in segments})
            length = sum(mm(item.GetLength()) for item in segments)
            row = {
                "length_mm": round(length, 3),
                "minimum_width_mm": round(min(widths), 3) if widths else None,
                "maximum_width_mm": round(max(widths), 3) if widths else None,
                "via_count": len(vias),
                "layers": layers,
                "segment_count": len(segments),
            }
            group_rows[net] = row
            required_width = MINIMUM_WIDTH_MM[group]
            def near(point: pcbnew.VECTOR2I,
                     other: pcbnew.VECTOR2I,
                     tolerance_mm: float = 0.02) -> bool:
                return (abs(mm(point.x - other.x)) <= tolerance_mm and
                        abs(mm(point.y - other.y)) <= tolerance_mm)

            def is_local_pad_escape(segment: pcbnew.PCB_TRACK) -> bool:
                """Allow only a short pad-to-via neck before a wide trunk.

                Fine-pitch IC/connector pads cannot physically launch at the
                full switch/high-current trunk width.  The exception is
                deliberately narrow: one endpoint must be this net's pad, the
                other a via, and the segment may be no longer than 3 mm.
                Via-to-via and free-junction narrow trunks remain errors.
                """
                if mm(segment.GetLength()) > 3.0:
                    return False
                endpoints = (segment.GetStart(), segment.GetEnd())
                pad_end = any(
                    pad.GetNetname() == net and
                    any(near(endpoint, pad.GetPosition())
                        for endpoint in endpoints)
                    for pad in pads)
                via_end = any(
                    via.GetNetname() == net and
                    any(near(endpoint, via.GetPosition())
                        for endpoint in endpoints)
                    for via in vias)
                return pad_end and via_end

            narrow = [segment for segment in segments
                      if mm(segment.GetWidth()) + 1e-6 < required_width]
            unacceptable = narrow
            if group in ("switch", "high_current"):
                unacceptable = [segment for segment in narrow
                                if not is_local_pad_escape(segment)]
            if unacceptable:
                narrowest = min(mm(item.GetWidth()) for item in unacceptable)
                errors.append(
                    f"WIDTH_{net}: {narrowest:.3f} mm below "
                    f"{required_width:.3f} mm outside local pad escape")
            if group in ("rf", "crystal") and vias:
                errors.append(f"VIA_{net}: expected no vias, found {len(vias)}")
        report["groups"][group] = group_rows

    rf = report["groups"]["rf"]["RX_RF"]
    if rf["length_mm"] > 15.0:
        errors.append(f"RF_LENGTH_RX_RF: {rf['length_mm']:.3f} mm exceeds 15.000 mm")
    if rf["segment_count"] and rf["layers"] != ["B.Cu"]:
        errors.append(f"RF_LAYER_RX_RF: expected B.Cu only, found {rf['layers']}")

    for net, row in report["groups"]["crystal"].items():
        if row["length_mm"] > 10.0:
            errors.append(
                f"CRYSTAL_LENGTH_{net}: {row['length_mm']:.3f} mm exceeds 10.000 mm")

    for side in ("", "_MCU"):
        positive = report["groups"]["usb"][f"USB_D+{side}"]
        negative = report["groups"]["usb"][f"USB_D-{side}"]
        skew = abs(positive["length_mm"] - negative["length_mm"])
        if positive["segment_count"] and negative["segment_count"] and skew > 1.0:
            errors.append(f"USB_SKEW{side}: {skew:.3f} mm exceeds 1.000 mm")
        if positive["via_count"] != negative["via_count"]:
            errors.append(
                f"USB_VIA_MISMATCH{side}: D+={positive['via_count']} D-={negative['via_count']}")

    report["errors"] = errors
    return report, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", nargs="?", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--json", type=Path, help="write the full audit as JSON")
    args = parser.parse_args()
    report, errors = audit(args.board)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
