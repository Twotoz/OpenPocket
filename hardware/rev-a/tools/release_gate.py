#!/usr/bin/env python3
"""Fail closed unless Revision-A source and order artifacts are coherent."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import pcbnew


REV = Path(__file__).resolve().parents[1]
ROOT = REV.parents[1]
STATUS = REV / "release-status.json"
BOARD = REV / "openpocket-rev-a.kicad_pcb"
SCHEMATIC = REV / "openpocket-rev-a.kicad_sch"
PROJECT = REV / "openpocket-rev-a.kicad_pro"
AMT = ROOT / "display" / "amt630a-openpocket"
OUT = ROOT / "manufacturing"
BAD_BOM_WORDS = ("tbd", "variant tbd", "generic", "unknown", "provisional")
REQUIRED_NETCLASSES = {
    "FinePitch", "DigitalFast", "USB_Preliminary", "AnalogVideo",
    "RF_Preliminary", "PowerLogic", "Power", "HighCurrent", "SwitchNode",
    "BacklightHV", "Ground", "Default",
}


def close_mm(actual: float, expected: float, tolerance: float = 0.01) -> bool:
    return abs(actual - expected) <= tolerance


def check_board_mechanics(errors: list[str]) -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    if board.GetCopperLayerCount() != 8:
        errors.append(
            f"COPPER_LAYER_COUNT: expected 8, found {board.GetCopperLayerCount()}")
    expected_layers = ("F.Cu", "GND1", "SIG1", "SIG2", "SIG3", "SIG4", "GND2", "B.Cu")
    copper_ids = [pcbnew.F_Cu]
    copper_ids.extend(pcbnew.In1_Cu + 2 * index for index in range(6))
    copper_ids.append(pcbnew.B_Cu)
    actual_layers = tuple(board.GetLayerName(layer) for layer in copper_ids)
    if actual_layers != expected_layers:
        errors.append(
            f"COPPER_LAYER_STACK: expected {expected_layers}, found {actual_layers}")

    outline = board.GetBoardEdgesBoundingBox()
    # KiCad includes half of the 0.10 mm Edge.Cuts stroke in this bounding box.
    width = pcbnew.ToMM(outline.GetWidth()) - 0.10
    height = pcbnew.ToMM(outline.GetHeight()) - 0.10
    if not close_mm(width, 115.0) or not close_mm(height, 72.0):
        errors.append(
            f"BOARD_SIZE: expected 115.00 x 72.00 mm, found {width:.2f} x {height:.2f} mm")

    connector = board.FindFootprintByReference("J1")
    if connector is None:
        errors.append("J1_MECHANICAL: footprint missing")
    else:
        position = connector.GetPosition()
        pin1 = next((pad for pad in connector.Pads() if pad.GetNumber() == "1"), None)
        if (not close_mm(pcbnew.ToMM(position.x), 29.75) or
                not close_mm(pcbnew.ToMM(position.y), 62.00) or
                not close_mm(connector.GetOrientationDegrees(), 180.0)):
            errors.append(
                "J1_MECHANICAL: expected center (29.75, 62.00) mm at 180 degrees")
        if pin1 is None or not close_mm(pcbnew.ToMM(pin1.GetPosition().x), 20.00):
            errors.append("J1_PIN1_X: expected pin 1 at x=20.00 mm")

    for reference in ("J2", "J12"):
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            errors.append(f"{reference}_MECHANICAL: footprint missing")
        elif footprint.GetLayer() != pcbnew.F_Cu:
            errors.append(f"{reference}_SIDE: expected top-side placement")

    if board.FindFootprintByReference("J10") is not None:
        errors.append("RF_STUB_J10: legacy coax-solder branch must be absent")
    receiver = board.FindFootprintByReference("MOD1")
    antenna = board.FindFootprintByReference("J11")
    if receiver is None or antenna is None:
        errors.append("RF_CONNECTOR_MECHANICAL: MOD1 or J11 missing")
    elif receiver.GetLayer() != pcbnew.B_Cu or antenna.GetLayer() != pcbnew.B_Cu:
        errors.append("RF_CONNECTOR_SIDE: MOD1 and J11 must both be bottom-side")
    else:
        receiver_rf = next((pad for pad in receiver.Pads()
                            if pad.GetNumber() == "2"), None)
        antenna_rf = next((pad for pad in antenna.Pads()
                           if pad.GetNumber() == "1"), None)
        if receiver_rf is None or antenna_rf is None:
            errors.append("RF_CONNECTOR_PAD: expected MOD1.2 and J11.1")
        else:
            dx = pcbnew.ToMM(receiver_rf.GetPosition().x - antenna_rf.GetPosition().x)
            dy = pcbnew.ToMM(receiver_rf.GetPosition().y - antenna_rf.GetPosition().y)
            if (dx * dx + dy * dy) ** 0.5 > 10.0:
                errors.append("RF_CONNECTOR_DISTANCE: RF pads exceed 10.0 mm separation")


def check_cpl_placement(errors: list[str], rows: list[dict[str, str]]) -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    for row in rows:
        reference = row["Designator"]
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            errors.append(f"CPL_FOOTPRINT_MISSING: {reference}")
            continue
        position = footprint.GetPosition()
        expected_x = pcbnew.ToMM(position.x)
        expected_y = pcbnew.ToMM(position.y)
        actual_x = float(row["Mid X"].removesuffix("mm"))
        actual_y = float(row["Mid Y"].removesuffix("mm"))
        expected_side = "Bottom" if footprint.GetLayer() == pcbnew.B_Cu else "Top"
        expected_rotation = footprint.GetOrientationDegrees() % 360.0
        actual_rotation = float(row["Rotation"]) % 360.0
        if (not close_mm(actual_x, expected_x, 0.001) or
                not close_mm(actual_y, expected_y, 0.001) or
                row["Layer"] != expected_side or
                not close_mm(actual_rotation, expected_rotation, 0.05)):
            errors.append(
                f"CPL_PLACEMENT_{reference}: CPL=({actual_x:.3f}, {actual_y:.3f}, "
                f"{row['Layer']}, {actual_rotation:.1f}) PCB=({expected_x:.3f}, "
                f"{expected_y:.3f}, {expected_side}, {expected_rotation:.1f})")


def check_pin_audit(errors: list[str], reference: str, path: Path) -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        errors.append(f"PIN_AUDIT_FOOTPRINT_MISSING: {reference}")
        return
    pads = {pad.GetNumber(): pad for pad in footprint.Pads()}
    for row in table(path):
        pin = row["pin"]
        if pin not in pads:
            errors.append(f"PIN_AUDIT_PAD_MISSING_{reference}: {pin}")
            continue
        position = pads[pin].GetPosition()
        actual_x = pcbnew.ToMM(position.x)
        actual_y = pcbnew.ToMM(position.y)
        documented_x = float(row["pad_x_mm"])
        documented_y = float(row["pad_y_mm"])
        if (not close_mm(actual_x, documented_x, 0.001) or
                not close_mm(actual_y, documented_y, 0.001)):
            errors.append(
                f"PIN_AUDIT_COORD_{reference}_{pin}: document=({documented_x:.3f}, "
                f"{documented_y:.3f}) PCB=({actual_x:.3f}, {actual_y:.3f})")


def table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    data = json.loads(STATUS.read_text(encoding="utf-8"))
    errors: list[str] = []
    for source in (PROJECT, SCHEMATIC, BOARD):
        if not source.is_file() or source.stat().st_size < 1000:
            errors.append(f"MISSING_OR_EMPTY_SOURCE: {source.name}")
    if BOARD.is_file():
        check_board_mechanics(errors)
    for blocker in data["blockers"]:
        if not blocker["resolved"]:
            errors.append(f"{blocker['id']}: {blocker['required_evidence']}")
    if not data.get("manufacturing_release_allowed", False):
        errors.append("RELEASE_FLAG: manufacturing_release_allowed is false")

    if PROJECT.is_file():
        project = json.loads(PROJECT.read_text(encoding="utf-8"))
        settings = project.get("net_settings", {})
        classes = {row.get("name") for row in settings.get("classes", [])}
        missing_classes = REQUIRED_NETCLASSES - classes
        if missing_classes:
            errors.append(f"NETCLASSES_MISSING: {sorted(missing_classes)}")
        assignments = {
            row.get("pattern"): row.get("netclass")
            for row in settings.get("netclass_patterns", [])
        }
        for net, expected in {
            "GND": "Ground", "RX_RF": "RF_Preliminary",
            "USB_D+": "USB_Preliminary", "VRX_VIDEO_RAW": "AnalogVideo",
            "SYS_SWITCHED": "HighCurrent", "BL_SW": "SwitchNode",
            "LCD_DCLK": "FinePitch",
        }.items():
            if assignments.get(net) != expected:
                errors.append(
                    f"NETCLASS_ASSIGNMENT_{net}: expected {expected}, "
                    f"found {assignments.get(net)}")

    with tempfile.TemporaryDirectory(prefix="openpocket-gate-") as temporary:
        temporary = Path(temporary)
        for kind, source in (("sch", SCHEMATIC), ("pcb", BOARD)):
            report = temporary / f"{kind}.rpt"
            command = ["kicad-cli", kind, "erc" if kind == "sch" else "drc",
                       "-o", str(report), "--severity-all"]
            if kind == "pcb":
                command.append("--all-track-errors")
            command.extend(("--exit-code-violations", str(source)))
            result = subprocess.run(command, cwd=ROOT, text=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            text = report.read_text(errors="replace") if report.exists() else result.stdout
            if result.returncode or ("0  Errors 0  Warnings" not in text if kind == "sch"
                                     else ("Found 0 DRC violations" not in text or
                                           "Found 0 unconnected pads" not in text)):
                errors.append(f"KICAD_{kind.upper()}_GATE: {result.stdout.strip()}")
        routing_report = temporary / "routing-audit.json"
        routing = subprocess.run(
            [sys.executable, str(REV / "tools" / "routing_audit.py"),
             str(BOARD), "--json", str(routing_report)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if routing.returncode:
            detail = routing_report.read_text(errors="replace") if routing_report.exists() else routing.stdout
            errors.append(f"CRITICAL_ROUTING_GATE: {detail[-4000:]}")
        netlist_report = temporary / "netlist-audit.json"
        netlist = subprocess.run(
            [sys.executable, str(REV / "tools" / "netlist_audit.py"),
             "--schematic", str(SCHEMATIC), "--board", str(BOARD),
             "--json", str(netlist_report)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if netlist.returncode:
            detail = netlist_report.read_text(errors="replace") if netlist_report.exists() else netlist.stdout
            errors.append(f"SCHEMATIC_PCB_NETLIST_GATE: {detail[-4000:]}")

    bom = table(REV / "bom-jlcpcb.csv")
    cpl = table(REV / "cpl-jlcpcb.csv")
    check_pin_audit(errors, "MOD1", REV / "rx5808-pin-audit.csv")
    check_pin_audit(errors, "J12", REV / "microsd-pin-audit.csv")
    populated = {row["Designator"] for row in bom if row["DNP"] == "no"}
    placed = {row["Designator"] for row in cpl}
    if "J11" not in populated or "J10" in {row["Designator"] for row in bom}:
        errors.append("RF_CONNECTOR_BOM: populate J11 and omit legacy J10")
    check_cpl_placement(errors, cpl)
    if populated != placed:
        errors.append(f"BOM_CPL_MISMATCH: bom-only={sorted(populated-placed)} "
                      f"cpl-only={sorted(placed-populated)}")
    for row in bom:
        if row["DNP"] != "no":
            continue
        joined = " ".join(row.values()).lower()
        if any(word in joined for word in BAD_BOM_WORDS):
            errors.append(f"BOM_UNRESOLVED: {row['Designator']}")
        for field in ("Manufacturer", "MPN", "LCSC", "Package"):
            if not row[field].strip():
                errors.append(f"BOM_EMPTY_{field.upper()}: {row['Designator']}")

    binary = AMT / "build" / "amt630a-openpocket-er-tft050a3-2.bin"
    checksum = AMT / "build" / "amt630a-openpocket-er-tft050a3-2.bin.sha256"
    if not binary.is_file() or binary.stat().st_size > 65536:
        errors.append("AMT_BINARY: missing or exceeds W25X05 capacity")
    elif not checksum.is_file() or checksum.read_text().split()[0] != digest(binary):
        errors.append("AMT_CHECKSUM: binary/checksum mismatch")
    test = subprocess.run(["make", "-C", str(AMT), "test"], cwd=ROOT,
                          text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    if test.returncode:
        errors.append("AMT_TESTS: " + test.stdout[-1000:])

    required = {
        "gerbers/openpocket-rev-a-F_Cu.gtl",
        "gerbers/openpocket-rev-a-GND1.g1",
        "gerbers/openpocket-rev-a-SIG1.g2",
        "gerbers/openpocket-rev-a-SIG2.g3",
        "gerbers/openpocket-rev-a-SIG3.g4",
        "gerbers/openpocket-rev-a-SIG4.g5",
        "gerbers/openpocket-rev-a-GND2.g6",
        "gerbers/openpocket-rev-a-B_Cu.gbl",
        "gerbers/openpocket-rev-a-F_Mask.gts",
        "gerbers/openpocket-rev-a-B_Mask.gbs",
        "gerbers/openpocket-rev-a-F_Paste.gtp",
        "gerbers/openpocket-rev-a-B_Paste.gbp",
        "gerbers/openpocket-rev-a-F_Silkscreen.gto",
        "gerbers/openpocket-rev-a-B_Silkscreen.gbo",
        "gerbers/openpocket-rev-a-Edge_Cuts.gm1",
        "gerbers/openpocket-rev-a.drl",
        "gerbers/openpocket-rev-a-drl_map.gbr",
        "gerbers/openpocket-rev-a-job.gbrjob",
        "assembly/bom-jlcpcb.csv",
        "assembly/cpl-jlcpcb.csv",
        "drawings/openpocket-rev-a.step",
        "drawings/openpocket-rev-a-schematic.pdf",
        "firmware/amt630a-openpocket-er-tft050a3-2.bin",
        "firmware/amt630a-openpocket-er-tft050a3-2.bin.sha256",
        "documentation/factory-test.md",
        "documentation/first-power-up.md",
        "documentation/routing-constraints.md",
        "documentation/stackup.md",
        "inspection/openpocket-rev-a-erc.rpt",
        "inspection/openpocket-rev-a-drc.rpt",
        "inspection/openpocket-rev-a-netlist-audit.json",
        "inspection/openpocket-rev-a-routing-audit.json",
        "PACKAGE-SHA256SUMS",
    }
    for zip_name in ("openpocket-rev-a-jlcpcb.zip",
                     "openpocket-rev-a-pcbway.zip"):
        path = OUT / zip_name
        if not path.is_file():
            errors.append(f"MISSING_PACKAGE: {zip_name}")
            continue
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            missing = required - names
            if missing:
                errors.append(f"PACKAGE_CONTENTS_{zip_name}: {sorted(missing)}")
            empty = sorted(
                name for name in required & names
                if archive.getinfo(name).file_size == 0
            )
            if empty:
                errors.append(f"PACKAGE_EMPTY_{zip_name}: {empty}")
            job_name = "gerbers/openpocket-rev-a-job.gbrjob"
            if job_name in names:
                job = json.loads(archive.read(job_name))
                specs = job.get("GeneralSpecs", {})
                if (specs.get("LayerNumber") != 8 or
                        specs.get("BoardThickness") != 1.0 or
                        specs.get("Finish") != "ENIG"):
                    errors.append(f"GERBER_JOB_SPECS_{zip_name}: {specs}")
                copper_functions = {
                    row.get("FileFunction") for row in job.get("FilesAttributes", [])
                    if str(row.get("FileFunction", "")).startswith("Copper,")
                }
                expected_functions = {
                    "Copper,L1,Top", "Copper,L2,Inr", "Copper,L3,Inr",
                    "Copper,L4,Inr", "Copper,L5,Inr", "Copper,L6,Inr",
                    "Copper,L7,Inr", "Copper,L8,Bot",
                }
                if copper_functions != expected_functions:
                    errors.append(
                        f"GERBER_COPPER_FUNCTIONS_{zip_name}: {sorted(copper_functions)}")
                stack_thickness = sum(
                    float(row.get("Thickness", 0.0))
                    for row in job.get("MaterialStackup", []))
                if not close_mm(stack_thickness, 1.0, 0.001):
                    errors.append(
                        f"GERBER_STACK_THICKNESS_{zip_name}: {stack_thickness:.3f} mm")
            drill_name = "gerbers/openpocket-rev-a.drl"
            if drill_name in names:
                drill = archive.read(drill_name).decode("ascii", errors="replace")
                if "M48" not in drill or "METRIC" not in drill or "T1" not in drill:
                    errors.append(f"EXCELLON_HEADER_{zip_name}: invalid drill header")

    if errors:
        print("OPENPOCKET_REV_A_RELEASE=BLOCKED")
        for error in errors:
            print(f"BLOCKER={error}")
        return 2
    print("OPENPOCKET_REV_A_RELEASE=ENGINEERING_DESIGN_COMPLETE")
    print("PREFABRICATION_VERIFICATION=PASSED")
    print("FIRST_ARTICLE_PHYSICAL_ACCEPTANCE=PENDING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
