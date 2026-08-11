#!/usr/bin/env python3
"""Import a Freerouting session while preserving mechanical PCB invariants."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import pcbnew


REV = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = REV / "openpocket-rev-a.kicad_pcb"


def _ses_tokens(text: str) -> list[str]:
    return re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', text)


def _ses_atom(token: str) -> str:
    if token.startswith('"'):
        return bytes(token[1:-1], "utf-8").decode("unicode_escape")
    return token


def _parse_ses(text: str) -> list:
    """Parse the small Specctra S-expression subset emitted by Freerouting."""
    root: list = []
    stack = [root]
    for token in _ses_tokens(text):
        if token == "(":
            item: list = []
            stack[-1].append(item)
            stack.append(item)
        elif token == ")":
            if len(stack) == 1:
                raise ValueError("unexpected ')' in SES")
            stack.pop()
        else:
            stack[-1].append(_ses_atom(token))
    if len(stack) != 1:
        raise ValueError("unterminated expression in SES")
    if len(root) != 1 or not root[0] or root[0][0] != "session":
        raise ValueError("SES does not contain one session expression")
    return root[0]


def _child(node: list, name: str) -> list:
    for item in node:
        if isinstance(item, list) and item and item[0] == name:
            return item
    raise ValueError(f"SES is missing {name!r}")


def _fallback_import(
    board: pcbnew.BOARD,
    session: Path,
    excluded_nets: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    """Import Freerouting paths with strict net/layer/geometry validation.

    KiCad 9 rejects otherwise valid sessions made from benchmark DSNs where
    already-reviewed nets were deliberately omitted.  Recreate only the
    explicit network_out copper here.  Existing copper is retained for nets
    absent from network_out, or explicitly excluded by the caller, and
    replaced for the remaining nets present in it.
    """
    tree = _parse_ses(session.read_text(encoding="utf-8"))
    placement = _child(tree, "placement")
    placement_resolution = _child(placement, "resolution")
    if (len(placement_resolution) != 3 or
            placement_resolution[1] != "um"):
        raise ValueError("only SES micrometre placement resolution is supported")
    placement_units_per_mm = float(placement_resolution[2]) * 1000.0
    ses_placements: dict[str, tuple[float, float, bool]] = {}
    for component in placement[1:]:
        if (not isinstance(component, list) or not component or
                component[0] != "component"):
            continue
        # KiCad omits the footprint-library identifier for generated
        # mounting-hole footprints, so their first place follows component
        # directly instead of occupying index 2.
        place_items = component[1:] if isinstance(component[1], list) \
            else component[2:]
        for place in place_items:
            if (not isinstance(place, list) or len(place) < 6 or
                    place[0] != "place"):
                raise ValueError("unsupported SES placement item")
            reference = str(place[1])
            if reference in ses_placements:
                raise ValueError(f"duplicate SES placement for {reference}")
            side = str(place[4])
            if side not in ("front", "back"):
                raise ValueError(f"unsupported SES side {side!r}")
            ses_placements[reference] = (
                float(place[2]) / placement_units_per_mm,
                -float(place[3]) / placement_units_per_mm,
                side == "back",
            )
    board_placements = {
        footprint.GetReference(): (
            pcbnew.ToMM(footprint.GetPosition().x),
            pcbnew.ToMM(footprint.GetPosition().y),
            bool(footprint.IsFlipped()),
        )
        for footprint in board.GetFootprints()
    }
    if set(ses_placements) != set(board_placements):
        raise ValueError("SES and PCB footprint reference sets do not match")
    for reference, expected in board_placements.items():
        actual = ses_placements[reference]
        if (abs(actual[0] - expected[0]) > 0.0011 or
                abs(actual[1] - expected[1]) > 0.0011 or
                actual[2] != expected[2]):
            raise ValueError(
                f"SES placement mismatch for {reference}: "
                f"SES={actual}, PCB={expected}")
    routes = _child(tree, "routes")
    resolution = _child(routes, "resolution")
    if len(resolution) != 3 or resolution[1] != "um":
        raise ValueError("only SES micrometre resolution is supported")
    units_per_um = float(resolution[2])
    if units_per_um <= 0:
        raise ValueError("invalid SES resolution")
    units_per_mm = units_per_um * 1000.0
    library = _child(routes, "library_out")
    via_sizes: dict[str, tuple[float, float]] = {}
    via_pattern = re.compile(r"_(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)_um$")
    for item in library[1:]:
        if not isinstance(item, list) or not item or item[0] != "padstack":
            continue
        name = str(item[1])
        match = via_pattern.search(name)
        if not match:
            raise ValueError(f"unsupported SES via padstack {name!r}")
        via_sizes[name] = (float(match.group(1)) / 1000.0,
                           float(match.group(2)) / 1000.0)
    network = _child(routes, "network_out")
    board_nets = {
        net.GetNetname(): net
        for net in board.GetNetInfo().NetsByName().values()
        if net.GetNetname()
    }
    routed_names = {
        str(item[1]) for item in network[1:]
        if isinstance(item, list) and len(item) >= 2 and item[0] == "net"
    }
    unknown_nets = routed_names - set(board_nets)
    if unknown_nets:
        raise ValueError(f"SES contains unknown nets: {sorted(unknown_nets)}")
    unknown_exclusions = excluded_nets - set(board_nets)
    if unknown_exclusions:
        raise ValueError(
            f"excluded nets are absent from the PCB: {sorted(unknown_exclusions)}")
    routed_names -= excluded_nets
    # A production DSN may mark generator-reviewed copper as ``protect``.
    # Freerouting echoes that copper into network_out and can quantize or
    # neck it while serializing the SES.  Keep the authoritative KiCad items
    # for every net that contains protected session copper and import only
    # newly routed items.  Benchmark sessions contain no protected items and
    # retain the original replace-per-net behaviour.
    protected_names: set[str] = set()
    for net_node in network[1:]:
        if (not isinstance(net_node, list) or len(net_node) < 2 or
                net_node[0] != "net"):
            continue
        if str(net_node[1]) in excluded_nets:
            continue
        if any(isinstance(item, list) and
               ((item[0] == "wire" and len(item) == 3 and
                 item[2] == ["type", "protect"]) or
                (item[0] == "via" and len(item) == 5 and
                 item[4] == ["type", "protect"]))
               for item in net_node[2:]):
            protected_names.add(str(net_node[1]))
    for track in list(board.GetTracks()):
        if (track.GetNetname() in routed_names and
                track.GetNetname() not in protected_names):
            board.Delete(track)
    segment_count = 0
    via_count = 0
    for net_node in network[1:]:
        if not isinstance(net_node, list) or not net_node:
            continue
        if net_node[0] != "net" or len(net_node) < 2:
            raise ValueError(f"unsupported network_out item {net_node[:2]!r}")
        net_name = str(net_node[1])
        if net_name in excluded_nets:
            continue
        net = board_nets[net_name]
        for item in net_node[2:]:
            if not isinstance(item, list) or not item:
                raise ValueError(f"invalid route item on {net_name}")
            if item[0] == "wire":
                if (len(item) not in (2, 3) or
                        not isinstance(item[1], list)):
                    raise ValueError(f"unsupported wire on {net_name}")
                if (len(item) == 3 and
                        item[2] != ["type", "protect"]):
                    raise ValueError(f"unsupported wire property on {net_name}")
                if len(item) == 3:
                    # Already present in the authoritative board.
                    continue
                path = item[1]
                if len(path) < 7 or path[0] != "path" or len(path[3:]) % 2:
                    raise ValueError(f"invalid path on {net_name}")
                layer_name = str(path[1])
                if layer_name in ("GND1", "GND2"):
                    raise ValueError(
                        f"signal path on protected plane {layer_name}")
                layer_id = board.GetLayerID(layer_name)
                if layer_id < 0 or not board.IsLayerEnabled(layer_id):
                    raise ValueError(f"unknown/disabled SES layer {layer_name!r}")
                width_mm = float(path[2]) / units_per_mm
                points = [
                    (float(path[i]) / units_per_mm,
                     -float(path[i + 1]) / units_per_mm)
                    for i in range(3, len(path), 2)
                ]
                for start, end in zip(points, points[1:]):
                    if start == end:
                        continue
                    segment = pcbnew.PCB_TRACK(board)
                    segment.SetStart(pcbnew.VECTOR2I_MM(*start))
                    segment.SetEnd(pcbnew.VECTOR2I_MM(*end))
                    segment.SetLayer(layer_id)
                    segment.SetWidth(pcbnew.FromMM(width_mm))
                    segment.SetNet(net)
                    board.Add(segment)
                    segment_count += 1
            elif item[0] == "via":
                if len(item) not in (4, 5):
                    raise ValueError(f"unsupported via on {net_name}")
                if (len(item) == 5 and
                        item[4] != ["type", "protect"]):
                    raise ValueError(f"unsupported via property on {net_name}")
                if len(item) == 5:
                    # Already present in the authoritative board.
                    continue
                padstack = str(item[1])
                if padstack not in via_sizes:
                    raise ValueError(f"undefined SES via padstack {padstack!r}")
                diameter_mm, drill_mm = via_sizes[padstack]
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I_MM(
                    float(item[2]) / units_per_mm,
                    -float(item[3]) / units_per_mm))
                via.SetWidth(pcbnew.FromMM(diameter_mm))
                via.SetDrill(pcbnew.FromMM(drill_mm))
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                via.SetNet(net)
                board.Add(via)
                via_count += 1
            else:
                raise ValueError(f"unsupported route item {item[0]!r}")
    return segment_count, via_count


def footprint_state(board: pcbnew.BOARD) -> dict[str, tuple[int, int, bool]]:
    return {
        footprint.GetReference(): (
            # SES import may quantize a coordinate by one internal KiCad unit
            # (0.001 mm); compare at the mechanical precision of the board.
            round(footprint.GetPosition().x, -1),
            round(footprint.GetPosition().y, -1),
            bool(footprint.IsFlipped()),
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
    parser.add_argument(
        "--fallback-parser", action="store_true",
        help=("strictly import explicit SES paths/vias when KiCad rejects a "
              "session produced from a deliberately filtered benchmark DSN"),
    )
    parser.add_argument(
        "--exclude-net", action="append", default=[], metavar="NET",
        help=("retain the PCB's existing copper for NET instead of importing "
              "that net from the SES; repeat for multiple nets"),
    )
    args = parser.parse_args()
    if not args.session.is_file() or args.session.stat().st_size == 0:
        raise SystemExit(f"missing or empty SES: {args.session}")

    board = pcbnew.LoadBoard(str(args.board))
    before_footprints = footprint_state(board)
    before_outline = outline_state(board)
    before_layers = board.GetCopperLayerCount()
    excluded_nets = frozenset(args.exclude_net)
    if excluded_nets and not args.fallback_parser:
        raise SystemExit("--exclude-net requires --fallback-parser")
    imported = False if excluded_nets else pcbnew.ImportSpecctraSES(
        board, str(args.session))
    if imported is False:
        if not args.fallback_parser:
            raise SystemExit("KiCad rejected the Freerouting session")
        segments, vias = _fallback_import(
            board, args.session, excluded_nets=excluded_nets)
        print("KICAD_NATIVE_IMPORT=SKIPPED" if excluded_nets else
              "KICAD_NATIVE_IMPORT=REJECTED")
        print("STRICT_FALLBACK_IMPORT=USED")
        if excluded_nets:
            print(f"EXCLUDED_NETS={','.join(sorted(excluded_nets))}")
        print(f"IMPORTED_SEGMENTS={segments}")
        print(f"IMPORTED_VIAS={vias}")

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
