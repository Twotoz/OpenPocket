#!/usr/bin/env python3
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "amt630a-openpocket-er-tft050a3-2.bin"
digest = hashlib.sha256(BINARY.read_bytes()).hexdigest()
commit = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    stdout=subprocess.PIPE, check=True).stdout.strip()
compiler = subprocess.run(
    ["sdcc", "--version"], text=True, stdout=subprocess.PIPE,
    check=True).stdout.splitlines()[0]
compiler_path = pathlib.Path(subprocess.run(
    ["sh", "-c", "command -v sdcc"], text=True, stdout=subprocess.PIPE,
    check=True).stdout.strip())
manifest = {
    "source_commit": commit,
    "compiler": compiler,
    "compiler_sha256": hashlib.sha256(compiler_path.read_bytes()).hexdigest(),
    "license": "MIT",
    "panel": "EastRising ER-TFT050A3-2 no-touch",
    "panel_timing": json.loads((ROOT / "panel-timing.json").read_text()),
    "cvbs_input": "CVBS1 after AT7456E",
    "standards": ["PAL", "NTSC"],
    "no_signal_policy": "TCON free-runs; blue substitution disabled; decoder resync pulse",
    "output_binary": str(BINARY.relative_to(ROOT)),
    "output_size": BINARY.stat().st_size,
    "output_sha256": digest,
}
(ROOT / "build-manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n")
