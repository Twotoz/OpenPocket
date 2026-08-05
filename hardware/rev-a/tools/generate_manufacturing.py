#!/usr/bin/env python3
"""Generate deterministic Rev-A fabrication and assembly deliverables."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


REV = Path(__file__).resolve().parents[1]
ROOT = REV.parents[1]
OUT = ROOT / "manufacturing"
BOARD = REV / "openpocket-rev-a.kicad_pcb"
SCHEMATIC = REV / "openpocket-rev-a.kicad_sch"
AMT = ROOT / "display" / "amt630a-openpocket"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_variant_boms() -> None:
    rows = list(csv.DictReader((REV / "bom-jlcpcb.csv").open(newline="")))
    fields = list(rows[0]) + ["Assembly variant"]
    for variant, consigned in (
        ("OPENPOCKET-REV-A-JLC-PREORDER", False),
        ("OPENPOCKET-REV-A-JLC-CONSIGNED-RX5808", True),
    ):
        path = OUT / "assembly" / f"{variant}-bom.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for source in rows:
                row = dict(source)
                row["Assembly variant"] = (
                    "CONSIGNED / FIXTURE PLACEMENT" if
                    consigned and row["Designator"] == "MOD1" else variant
                )
                writer.writerow(row)


def make_zip(name: str, members: list[Path]) -> Path:
    target = OUT / name
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(members, key=lambda item: item.as_posix()):
            info = zipfile.ZipInfo(path.relative_to(OUT).as_posix())
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return target


def main() -> int:
    if not BOARD.is_file() or not SCHEMATIC.is_file():
        raise SystemExit("KiCad sources are missing")
    if OUT.exists():
        shutil.rmtree(OUT)
    for directory in ("gerbers", "drawings", "assembly", "firmware",
                      "documentation", "inspection"):
        (OUT / directory).mkdir(parents=True, exist_ok=True)

    run("kicad-cli", "pcb", "export", "gerbers", "-o",
        str(OUT / "gerbers"), "-l",
        "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts",
        "--subtract-soldermask", str(BOARD))
    run("kicad-cli", "pcb", "export", "drill", "-o",
        str(OUT / "gerbers"), "--format", "excellon", "--generate-map",
        "--map-format", "gerberx2", str(BOARD))
    run("kicad-cli", "pcb", "export", "pos", "-o",
        str(OUT / "assembly" / "openpocket-rev-a-generic-pos.csv"),
        "--format", "csv", "--units", "mm", "--side", "both",
        "--exclude-dnp", str(BOARD))
    run("kicad-cli", "pcb", "export", "step", "-o",
        str(OUT / "drawings" / "openpocket-rev-a.step"), "--force",
        "--board-only", "--include-tracks", "--include-pads", "--include-zones",
        str(BOARD))
    run("kicad-cli", "sch", "export", "pdf", "-o",
        str(OUT / "drawings" / "openpocket-rev-a-schematic.pdf"),
        str(SCHEMATIC))
    for side, layers in (
        ("top", "F.Fab,F.Silkscreen,Edge.Cuts"),
        ("bottom", "B.Fab,B.Silkscreen,Edge.Cuts"),
        ("fabrication", "F.Fab,B.Fab,Edge.Cuts"),
    ):
        args = ["kicad-cli", "pcb", "export", "pdf", "-o",
                str(OUT / "drawings" / f"openpocket-rev-a-{side}.pdf"),
                "-l", layers, "--black-and-white", "--mode-single"]
        if side == "bottom":
            args.append("--mirror")
        run(*args, str(BOARD))
    for side in ("top", "bottom"):
        run("kicad-cli", "pcb", "render", "-o",
            str(OUT / "inspection" / f"openpocket-rev-a-{side}.png"),
            "--side", side, "--width", "1600", "--height", "1067",
            "--quality", "basic", str(BOARD))

    for name in ("bom-generic.csv", "bom-jlcpcb.csv", "cpl-generic.csv",
                 "cpl-jlcpcb.csv", "dnp.csv", "consigned-parts.csv",
                 "amt630a-pin-audit.csv", "rx5808-pin-audit.csv",
                 "microsd-pin-audit.csv"):
        copy(REV / name, OUT / "assembly" / name)
    write_variant_boms()

    for name in ("README.md", "gpio-map.md", "microsd.md", "wiring.md",
                 "power-budget.md", "routing-constraints.md",
                 "factory-test.md", "pcbway-notes.md", "jlcpcb-notes.md",
                 "first-power-up.md", "production-readiness.md"):
        copy(REV / name, OUT / "documentation" / name)
    for name in ("LICENSE", "README.md", "registers.md", "panel-timing.json",
                 "build-manifest.json"):
        copy(AMT / name, OUT / "firmware" / name)
    for name in ("amt630a-openpocket-er-tft050a3-2.bin",
                 "amt630a-openpocket-er-tft050a3-2.bin.sha256"):
        copy(AMT / "build" / name, OUT / "firmware" / name)

    package_files = [path for path in OUT.rglob("*") if path.is_file()]
    package_checksums = [f"{sha256(path)}  {path.relative_to(OUT).as_posix()}"
                         for path in sorted(package_files)]
    (OUT / "PACKAGE-SHA256SUMS").write_text(
        "\n".join(package_checksums) + "\n", encoding="utf-8")
    package_files.append(OUT / "PACKAGE-SHA256SUMS")
    jlc = make_zip("openpocket-rev-a-jlcpcb.zip", package_files)
    pcbway = make_zip("openpocket-rev-a-pcbway.zip", package_files)
    checksummed = [path for path in OUT.rglob("*") if path.is_file() and
                   path.name != "SHA256SUMS"]
    lines = [f"{sha256(path)}  {path.relative_to(OUT).as_posix()}"
             for path in sorted(checksummed)]
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"JLCPCB_PACKAGE={jlc}")
    print(f"PCBWAY_PACKAGE={pcbway}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
