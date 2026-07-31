import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class FirmwareTests(unittest.TestCase):
    def test_panel_timing_arithmetic(self):
        timing = json.loads((ROOT / "panel-timing.json").read_text())
        self.assertEqual(timing["horizontal_total"], 480 + 5 + 1 + 39)
        self.assertEqual(timing["vertical_total"], 272 + 8 + 1 + 7)
        refresh = 9_000_000 / (525 * 288)
        self.assertAlmostEqual(timing["refresh_hz"], refresh, places=6)

    def test_register_integrity_and_no_blue_screen(self):
        source = (ROOT / "src" / "registers.c").read_text()
        writes = [(int(a, 16), int(v, 16)) for a, v in
                  re.findall(r"\{0x([0-9a-f]{4}), 0x([0-9a-f]{2})\}", source)]
        self.assertGreater(len(writes), 100)
        seen = {}
        for address, value in writes:
            if address in seen:
                self.assertIn(address, {0xFED7})
            seen[address] = value
        self.assertEqual(seen[0xFC00], 0x00)
        self.assertEqual([seen[a] for a in range(0xFD34, 0xFD44)], [0x22] * 16)
        self.assertEqual(seen[0xFD50], 0x0F)
        self.assertEqual(seen[0xFEDC] & 0xD0, 0)
        self.assertEqual(seen[0xFED7] & 0xC3, 0)
        self.assertIn(0xFC98, seen)  # NTSC
        self.assertIn(0xFCC4, seen)  # PAL

    def test_state_machine_paths(self):
        source = (ROOT / "src" / "main.c").read_text()
        self.assertIn("current_standard == 0", source)
        self.assertIn("stable >= 4", source)
        self.assertIn("status_update(0x07", source)
        self.assertIn("register_write(0xfea0", source)

    def test_binary_manifest(self):
        binary = ROOT / "build" / "amt630a-openpocket-er-tft050a3-2.bin"
        manifest = json.loads((ROOT / "build-manifest.json").read_text())
        self.assertEqual(binary.stat().st_size, 65536)
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        self.assertEqual(manifest["output_sha256"], digest)
        self.assertEqual((ROOT / "build" /
                          (binary.name + ".sha256")).read_text().strip(), digest)

    def test_deterministic_rebuild(self):
        before = hashlib.sha256((ROOT / "build" /
            "amt630a-openpocket-er-tft050a3-2.bin").read_bytes()).hexdigest()
        subprocess.run(["make", "clean", "all"], cwd=ROOT, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        after = hashlib.sha256((ROOT / "build" /
            "amt630a-openpocket-er-tft050a3-2.bin").read_bytes()).hexdigest()
        self.assertEqual(before, after)

if __name__ == "__main__":
    unittest.main()
