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
                       "-o", str(report), str(source)]
            result = subprocess.run(command, cwd=ROOT, text=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            text = report.read_text(errors="replace") if report.exists() else result.stdout
            if result.returncode or ("0  Errors 0  Warnings" not in text if kind == "sch"
                                     else ("Found 0 DRC violations" not in text or
                                           "Found 0 unconnected pads" not in text)):
                errors.append(f"KICAD_{kind.upper()}_GATE: {result.stdout.strip()}")

    bom = table(REV / "bom-jlcpcb.csv")
    cpl = table(REV / "cpl-jlcpcb.csv")
    populated = {row["Designator"] for row in bom if row["DNP"] == "no"}
    placed = {row["Designator"] for row in cpl}
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
        "gerbers/openpocket-rev-a-GND.g1",
        "gerbers/openpocket-rev-a-PWR_SIG.g2",
        "gerbers/openpocket-rev-a-B_Cu.gbl",
        "assembly/bom-jlcpcb.csv",
        "assembly/cpl-jlcpcb.csv",
        "drawings/openpocket-rev-a.step",
        "drawings/openpocket-rev-a-schematic.pdf",
        "firmware/amt630a-openpocket-er-tft050a3-2.bin",
        "firmware/amt630a-openpocket-er-tft050a3-2.bin.sha256",
        "documentation/factory-test.md",
        "documentation/first-power-up.md",
        "documentation/routing-constraints.md",
        "PACKAGE-SHA256SUMS",
    }
    for zip_name in ("openpocket-rev-a-jlcpcb.zip",
                     "openpocket-rev-a-pcbway.zip"):
        path = OUT / zip_name
        if not path.is_file():
            errors.append(f"MISSING_PACKAGE: {zip_name}")
            continue
        with zipfile.ZipFile(path) as archive:
            missing = required - set(archive.namelist())
            if missing:
                errors.append(f"PACKAGE_CONTENTS_{zip_name}: {sorted(missing)}")

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
