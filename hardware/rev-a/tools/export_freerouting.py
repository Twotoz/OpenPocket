#!/usr/bin/env python3
"""Export a Specctra DSN while protecting the two ground-reference planes."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

import pcbnew


REV = Path(__file__).resolve().parents[1]


def _remove_blocks(text: str, needle: str) -> str:
    """Remove balanced Specctra blocks whose opening line contains *needle*."""
    while True:
        start = text.find(needle)
        if start < 0:
            return text
        line_start = text.rfind("\n", 0, start) + 1
        depth = 0
        end = None
        for index in range(line_start, len(text)):
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end is None:
            raise SystemExit(f"cannot remove unterminated DSN block {needle!r}")
        if end < len(text) and text[end] == "\n":
            end += 1
        text = text[:line_start] + text[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path,
                        default=REV / "openpocket-rev-a.kicad_pcb")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--benchmark", action="store_true",
        help=("omit the two reviewed battery seed routes from the DSN; "
              "use only for a placement-routing benchmark, never for import"),
    )
    parser.add_argument(
        "--protect-existing", action="store_true",
        help=("mark all existing generator-reviewed tracks/vias as protected "
              "so Freerouting cannot rip them up"),
    )
    parser.add_argument(
        "--omit-ground-network", action="store_true",
        help=("omit only the GND pin list from routing work while retaining "
              "existing GND planes/tracks/vias as protected obstacles"),
    )
    parser.add_argument(
        "--clearance-margin-um", type=int, default=0,
        help=("add a conservative margin to every Specctra copper-clearance "
              "rule without changing the authoritative KiCad netclasses"),
    )
    parser.add_argument(
        "--minimum-rule-width-um", type=int, default=0,
        help=("raise narrow Specctra class widths to this routing-only "
              "minimum; useful for keeping router-generated pad necks above "
              "the KiCad fabrication minimum"),
    )
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board))
    if board.GetCopperLayerCount() != 8:
        raise SystemExit("expected the reviewed eight-layer board")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.ExportSpecctraDSN(board, str(args.output)):
        raise SystemExit("KiCad failed to export Specctra DSN")
    text = args.output.read_text(encoding="utf-8")
    if args.clearance_margin_um < 0:
        raise SystemExit("clearance margin cannot be negative")
    if args.minimum_rule_width_um < 0:
        raise SystemExit("minimum rule width cannot be negative")
    if args.clearance_margin_um:
        text, count = re.subn(
            r"\(clearance (\d+)\)",
            lambda match: (f"(clearance "
                           f"{int(match.group(1)) + args.clearance_margin_um})"),
            text,
        )
        if count == 0:
            raise SystemExit("exported DSN contains no clearance rules")
    if args.minimum_rule_width_um:
        text, count = re.subn(
            r"\(width (\d+)\)",
            lambda match: (f"(width {max(int(match.group(1)), args.minimum_rule_width_um)})"),
            text,
        )
        if count == 0:
            raise SystemExit("exported DSN contains no width rules")
    for name in ("GND1", "GND2"):
        old = f"(layer {name}\n      (type signal)"
        new = f"(layer {name}\n      (type power)"
        if text.count(old) != 1:
            raise SystemExit(f"cannot protect {name} in exported DSN")
        text = text.replace(old, new, 1)
    if args.benchmark:
        # FreeRouting 2.2.x has a null-polyline bug when it reopens the two
        # branched, manually reviewed battery seed routes.  Keep them in the
        # authoritative KiCad PCB; omit only their existing wire/via records
        # from this disposable benchmark DSN so the router can measure the
        # remaining placement quality.  The netlist itself is untouched, so
        # BAT_RAW and BAT_CELL_NEG remain valid routing work for the tool.
        seed_nets = ("BAT_RAW", "BAT_CELL_NEG")
        text = "\n".join(
            line for line in text.splitlines()
            if not any(f"(net {net})" in line for net in seed_nets)
        ) + "\n"
        # The reviewed GND1/GND2 planes are already present in the
        # authoritative PCB.  They must not be treated as a giant
        # autoroutable Specctra network: doing so makes Freerouting spend most
        # of each pass recursively scoring the plane geometry and obscures the
        # signal-placement benchmark.  This disposable DSN therefore omits
        # only the GND network, its route records, and the two plane blocks.
        text = _remove_blocks(text, "    (net GND\n")
        text = _remove_blocks(text, "    (plane GND ")
        # These short critical nets are already fully connected by reviewed
        # generator copper.  Freerouting 2.3 counts a protected polyline as
        # an extra connection endpoint and otherwise queues a false
        # incomplete for each.  Omit them only from this disposable
        # benchmark; the authoritative KiCad board retains and DRC-checks
        # both routes.
        completed_reviewed_nets = ("USB_SHIELD", "AMT_CVBS1", "VBUS_RAW")
        for net_name in completed_reviewed_nets:
            text = _remove_blocks(text, f"    (net {net_name}\n")
        text = "\n".join(
            line for line in text.splitlines()
            if "(net GND)" not in line and
            not any(f"(net {net_name})" in line
                    for net_name in completed_reviewed_nets)
        ) + "\n"
    elif args.omit_ground_network:
        # Continuation routing must see every existing GND feature as an
        # obstacle, otherwise newly added traces can cross local ground
        # spokes/vias and short on the authoritative PCB.  Remove only the
        # network pin list that makes GND an unrouted task.  Keep the plane and
        # wiring records; --protect-existing converts their route records to
        # immutable obstacles below.
        text = _remove_blocks(text, "    (net GND\n")
    protected_items = 0
    if args.protect_existing:
        protected_items = text.count("(type route)")
        text = text.replace("(type route)", "(type protect)")
    args.output.write_text(text, encoding="utf-8")
    print(f"EXPORTED_DSN={args.output}")
    print("PROTECTED_PLANES=GND1,GND2")
    print(f"ROUTING_CLEARANCE_MARGIN_UM={args.clearance_margin_um}")
    print(f"ROUTING_MINIMUM_RULE_WIDTH_UM={args.minimum_rule_width_um}")
    if args.benchmark:
        print("BENCHMARK_OMITTED_EXISTING_ROUTE_NETS=BAT_RAW,BAT_CELL_NEG")
        print("BENCHMARK_OMITTED_GND_PLANES_AND_NET=GND,GND1,GND2")
        print("BENCHMARK_OMITTED_COMPLETED_REVIEWED_NETS="
              "USB_SHIELD,AMT_CVBS1,VBUS_RAW")
    elif args.omit_ground_network:
        print("OMITTED_GROUND_PINLIST=GND")
        print("PROTECTED_GROUND_COPPER=GND,GND1,GND2")
    if args.protect_existing:
        print(f"PROTECTED_EXISTING_ROUTE_ITEMS={protected_items}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
