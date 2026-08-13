#!/usr/bin/env python3
"""Compare the KiCad schematic netlist with every physical PCB pad."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pcbnew


REV = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMATIC = REV / "openpocket-rev-a.kicad_sch"
DEFAULT_BOARD = REV / "openpocket-rev-a.kicad_pcb"


def canonical(net: str) -> str:
    net = net[1:] if net.startswith("/") else net
    return "" if net.startswith("unconnected-(") else net


def audit(schematic: Path, board_path: Path) -> tuple[dict[str, object], list[str]]:
    with tempfile.TemporaryDirectory(prefix="openpocket-netlist-") as temporary:
        exported = Path(temporary) / "schematic.xml"
        result = subprocess.run(
            ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
             "-o", str(exported), str(schematic)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode or not exported.is_file():
            return {"export_output": result.stdout}, ["SCHEMATIC_NETLIST_EXPORT_FAILED"]
        root = ET.parse(exported).getroot()

    schematic_nodes: dict[tuple[str, str], str] = {}
    for net in root.findall("./nets/net"):
        name = canonical(net.attrib["name"])
        for node in net.findall("node"):
            schematic_nodes[(node.attrib["ref"], node.attrib["pin"])] = name

    board = pcbnew.LoadBoard(str(board_path))
    board_nodes: dict[tuple[str, str], str] = {}
    duplicate_board_pads: list[str] = []
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        for pad in footprint.Pads():
            pin = pad.GetNumber()
            if not pin:
                continue
            key = reference, pin
            net = canonical(pad.GetNetname())
            if key in board_nodes and board_nodes[key] != net:
                duplicate_board_pads.append(
                    f"{reference}.{pin}: {board_nodes[key]} versus {net}")
            board_nodes[key] = net

    errors: list[str] = []
    errors.extend(f"DUPLICATE_PCB_PAD_NET: {item}" for item in duplicate_board_pads)
    mismatches: list[str] = []
    missing_physical: list[str] = []
    extra_physical: list[str] = []
    fused_logical: list[str] = []
    for key, expected in sorted(schematic_nodes.items()):
        if key in board_nodes:
            actual = board_nodes[key]
            if actual != expected:
                mismatches.append(f"{key[0]}.{key[1]}: schematic={expected} PCB={actual}")
            continue
        represented = any(
            reference == key[0] and net == expected
            for (reference, _), net in board_nodes.items()
        )
        if represented:
            fused_logical.append(f"{key[0]}.{key[1]}={expected}")
        else:
            missing_physical.append(f"{key[0]}.{key[1]}={expected}")
    for key, actual in sorted(board_nodes.items()):
        if key not in schematic_nodes and actual:
            extra_physical.append(f"{key[0]}.{key[1]}={actual}")

    if mismatches:
        errors.append(f"NET_MISMATCH: {mismatches}")
    if missing_physical:
        errors.append(f"SCHEMATIC_PADS_MISSING_ON_PCB: {missing_physical}")
    if extra_physical:
        errors.append(f"PCB_PADS_MISSING_IN_SCHEMATIC: {extra_physical}")
    report: dict[str, object] = {
        "schematic": str(schematic),
        "board": str(board_path),
        "schematic_connected_nodes": sum(bool(net) for net in schematic_nodes.values()),
        "schematic_nc_nodes": sum(not net for net in schematic_nodes.values()),
        "pcb_connected_physical_pads": sum(bool(net) for net in board_nodes.values()),
        "fused_logical_pads": fused_logical,
        "mismatches": mismatches,
        "missing_physical_pads": missing_physical,
        "extra_physical_pads": extra_physical,
        "errors": errors,
    }
    return report, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schematic", type=Path, default=DEFAULT_SCHEMATIC)
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report, errors = audit(args.schematic, args.board)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
