#!/usr/bin/env python3
"""Generate the authoritative Rev-A schematic, PCB seed, and BOM tables."""
from __future__ import annotations

import csv
import functools
import json
import math
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOARD = ROOT / "openpocket-rev-a.kicad_pcb"
ROUTING = ROOT / "openpocket-rev-a.ses"
SCHEMATIC = ROOT / "openpocket-rev-a.kicad_sch"
LIBRARY = ROOT / "openpocket-rev-a.kicad_sym"
EASYEDA_LIBRARY = ROOT / "easyeda" / "openpocket-easyeda.kicad_sym"
EASYEDA_FOOTPRINTS = ROOT / "easyeda" / "openpocket-easyeda.pretty"
CUSTOM_FOOTPRINTS = ROOT / "openpocket-rev-a.pretty"
PLACEMENT_MANIFEST = ROOT / "placement-optimized.json"

BOARD_WIDTH = 115.0
BOARD_HEIGHT = 72.0

@dataclass
class Part:
    ref: str
    value: str
    manufacturer: str
    mpn: str
    lcsc: str
    package: str
    pins: list[tuple[str, str]]
    pin_numbers: list[str] | None
    x: float
    y: float
    side: str = "F"
    dnp: bool = False
    notes: str = ""
    rotation: float = 0.0

P: list[Part] = []

# These are routing constraints, not claims of final impedance or thermal
# sign-off.  USB and RF widths remain subject to the assembler's selected
# stack-up; high-current classes still require copper/temperature review.
# Keeping them in the generator prevents a generic-width autoroute from being
# mistaken for an engineering layout.
NET_CLASS_RULES = [
    ("FinePitch", dict(clearance=0.10, track_width=0.12,
                       via_diameter=0.45, via_drill=0.20,
                       diff_pair_width=0.12, diff_pair_gap=0.12)),
    ("DigitalFast", dict(clearance=0.12, track_width=0.15,
                         via_diameter=0.50, via_drill=0.25,
                         diff_pair_width=0.15, diff_pair_gap=0.15)),
    ("USB_Preliminary", dict(clearance=0.15, track_width=0.15,
                             via_diameter=0.45, via_drill=0.20,
                             diff_pair_width=0.15, diff_pair_gap=0.15)),
    ("AnalogVideo", dict(clearance=0.15, track_width=0.25,
                         via_diameter=0.60, via_drill=0.30,
                         diff_pair_width=0.20, diff_pair_gap=0.20)),
    # U.FL-R-SMT-1(10) has a 0.25 mm RF-to-ground land gap; keep the
    # preliminary RF rule aligned with that audited footprint geometry.
    ("RF_Preliminary", dict(clearance=0.25, track_width=0.25,
                            via_diameter=0.60, via_drill=0.30,
                            diff_pair_width=0.20, diff_pair_gap=0.20)),
    ("PowerLogic", dict(clearance=0.15, track_width=0.40,
                        via_diameter=0.70, via_drill=0.35,
                        diff_pair_width=0.20, diff_pair_gap=0.20)),
    ("Power", dict(clearance=0.15, track_width=0.80,
                   via_diameter=0.80, via_drill=0.40,
                   diff_pair_width=0.20, diff_pair_gap=0.20)),
    ("HighCurrent", dict(clearance=0.20, track_width=1.20,
                         via_diameter=1.00, via_drill=0.50,
                         diff_pair_width=0.20, diff_pair_gap=0.20)),
    ("SwitchNode", dict(clearance=0.20, track_width=0.80,
                        via_diameter=0.80, via_drill=0.40,
                        diff_pair_width=0.20, diff_pair_gap=0.20)),
    ("BacklightHV", dict(clearance=0.20, track_width=0.40,
                         via_diameter=0.70, via_drill=0.35,
                         diff_pair_width=0.20, diff_pair_gap=0.20)),
    ("Ground", dict(clearance=0.10, track_width=0.50,
                    via_diameter=0.70, via_drill=0.35,
                    diff_pair_width=0.20, diff_pair_gap=0.20)),
    ("Default", dict(clearance=0.10, track_width=0.20,
                     via_diameter=0.60, via_drill=0.30,
                     diff_pair_width=0.20, diff_pair_gap=0.20)),
]

NET_CLASS_MEMBERS = {
    "FinePitch": {
        *(f"LCD_{colour}{bit}" for colour in "RGB" for bit in range(8)),
        "LCD_DCLK", "LCD_DCLK_SRC", "LCD_DE", "LCD_DISP", "LCD_HSYNC",
        "LCD_VSYNC",
    },
    "DigitalFast": {
        "AMT_FLASH_C", "AMT_FLASH_C_CLK", "AMT_FLASH_C_MISO",
        "AMT_FLASH_C_MOSI", "AMT_FLASH_CLK", "AMT_FLASH_CLK_ESP",
        "AMT_FLASH_CS", "AMT_FLASH_CS_ESP", "AMT_FLASH_MISO",
        "AMT_FLASH_MISO_ESP", "AMT_FLASH_MOSI", "AMT_FLASH_MOSI_ESP",
        "AUDIO_I2S_BCLK", "AUDIO_I2S_DATA", "AUDIO_I2S_WS",
        "OSD_CS_3V3", "OSD_CS_5V", "OSD_MISO_3V3", "OSD_MISO_5V",
        "OSD_MOSI_3V3", "OSD_MOSI_5V", "OSD_SCLK_3V3", "OSD_SCLK_5V",
        "RX_CLK", "RX_CLK_MCU", "RX_DATA", "RX_DATA_MCU", "RX_LE",
        "RX_LE_MCU", "SD_CLK", "SD_CLK_MCU", "SD_CMD", "SD_CMD_MCU",
        "SD_D0", "SD_D0_MCU", "SD_DAT1", "SD_DAT2", "SD_DAT3",
    },
    "USB_Preliminary": {"USB_D+", "USB_D+_MCU", "USB_D-", "USB_D-_MCU"},
    "AnalogVideo": {
        "AMT_CVBS1", "AMT_CVBS_PRE", "AMT_VCOM", "OSD_VIDEO_BYP",
        "OSD_VIDEO_RAW", "TP_CVBS2", "TP_CVBS3", "VRX_VIDEO_COUPLED",
        "VRX_VIDEO_RAW", "VRX_VIDEO_TO_OSD",
    },
    "RF_Preliminary": {"RX_RF"},
    "PowerLogic": {
        "3V3_LOGIC", "3V3_SD", "5V_VCC", "AMT_CORE1", "AMT_CORE2",
        "AMT_CORE3", "BUZZER_5V", "BUZZER_LOW", "DISPLAY_3V3",
        "DISPLAY_3V3_A", "DISPLAY_3V3_D", "PANEL_3V3", "REGN", "SPK+",
        "SPK-", "BAT_NEG_SENSE", "PACK_NEG_SENSE",
    },
    "Power": {"5V_DISPLAY", "5V_ELRS", "5V_VIDEO", "5V_VIDEO_FILT"},
    "HighCurrent": {
        "BAT_CELL_NEG", "BAT_PROTECTED", "BAT_RAW", "PMID", "SYS_ALWAYS", "SYS_SWITCHED",
        "SYS_SWITCHED_5V", "VBUS_RAW", "VBUS_USB",
    },
    "SwitchNode": {"BL_SW", "CHG_SW", "DISP_SW", "L3V3_A", "L3V3_B",
                   "L5V_SW"},
    "BacklightHV": {"BL_LED_A", "BL_LED_K"},
    "Ground": {"GND"},
}

def add(ref, value, manufacturer, mpn, lcsc, package, pins, x, y,
        side="F", dnp=False, notes="", pin_numbers=None, rotation=0.0):
    if pin_numbers is not None and len(pin_numbers) != len(pins):
        raise ValueError(f"{ref}: pin number and connection counts differ")
    P.append(Part(ref, value, manufacturer, mpn, lcsc, package,
                  list(pins), list(pin_numbers) if pin_numbers else None,
                  x, y, side, dnp, notes, rotation))

def pin_items(part: Part):
    numbers = part.pin_numbers or [str(i) for i in range(1, len(part.pins) + 1)]
    return [(numbers[i], name, net) for i, (name, net) in enumerate(part.pins)]


@functools.cache
def easyeda_footprint_map() -> dict[str, str]:
    """Return the reviewed LCSC-to-land-pattern mapping in the local library."""
    if not EASYEDA_LIBRARY.exists():
        return {}
    source = EASYEDA_LIBRARY.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for match in re.finditer(r'"(C[0-9]+)"', source):
        start = source.rfind('\n  (symbol "', 0, match.start())
        if start < 0:
            continue
        block = source[start:match.end()]
        footprint = re.search(r'"Footprint"\s+"([^"]+)"', block)
        if footprint:
            result[match.group(1)] = footprint.group(1)
    return result


def footprint_id(part: Part) -> str:
    if part.ref == "J12":
        return "OpenPocket:TF-001A-P3"
    exact = easyeda_footprint_map().get(part.lcsc)
    if exact:
        return exact
    name = re.sub(r"[^A-Za-z0-9_.+-]", "_", part.package)
    return f"OpenPocket:{name}"


def generate_custom_footprints() -> None:
    """Emit reviewed footprints for mechanical/custom, non-catalogue parts."""
    CUSTOM_FOOTPRINTS.mkdir(parents=True, exist_ok=True)

    def write(name: str, body: list[str], attr: str = "smd") -> None:
        header = [
            f'(footprint "{name}"', '  (version 20240108)',
            '  (generator openpocket)', '  (layer "F.Cu")', f'  (attr {attr})',
            '  (property "Reference" "REF**" (at 0 -3 0) (layer "F.SilkS")',
            '    (effects (font (size 0.8 0.8) (thickness 0.12))))',
            f'  (property "Value" "{name}" (at 0 3 0) (layer "F.Fab")',
            '    (effects (font (size 0.8 0.8) (thickness 0.12))))',
        ]
        (CUSTOM_FOOTPRINTS / f"{name}.kicad_mod").write_text(
            "\n".join(header + body + [")", ""]), encoding="utf-8")

    write("TEST-PAD-1.0MM", [
        '  (pad "1" smd circle (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask"))'])
    write("0402", [
        '  (fp_rect (start -1 -0.55) (end 1 0.55) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
        '  (pad "1" smd roundrect (at -0.5 0) (size 0.55 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))',
        '  (pad "2" smd roundrect (at 0.5 0) (size 0.55 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))'])
    write("0603", [
        '  (fp_rect (start -1.4 -0.8) (end 1.4 0.8) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
        '  (pad "1" smd roundrect (at -0.75 0) (size 0.85 0.90) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))',
        '  (pad "2" smd roundrect (at 0.75 0) (size 0.85 0.90) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))'])
    write("SMD-D10", [
        '  (fp_rect (start -5.4 -5.4) (end 5.4 5.4) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
        '  (fp_circle (center 0 0) (end 5 0) (stroke (width 0.10) (type default)) (fill none) (layer "F.Fab"))',
        '  (fp_text user "+" (at -6.1 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        '  (pad "1" smd roundrect (at -4.35 0) (size 4.4 1.9) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.13))',
        '  (pad "2" smd roundrect (at 4.35 0) (size 4.4 1.9) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.13))'])
    write("Fiducial_1mm_Mask2mm", [
        '  (pad "" smd circle (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask") (solder_mask_margin 0.5))'])
    write("SMD-7.5x7.5", [
        '  (fp_rect (start -3.75 -3.75) (end 3.75 3.75) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
        '  (fp_rect (start -4 -4) (end 4 4) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
        '  (fp_circle (center 0 0) (end 2.4 0) (stroke (width 0.15) (type default)) (fill none) (layer "F.SilkS"))',
        '  (pad "1" smd roundrect (at -2.7 0) (size 2 2.2) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))',
        '  (pad "2" smd roundrect (at 2.7 0) (size 2 2.2) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))'])
    for count in (2, 4, 6, 22):
        pads = []
        pitch = 2.40 if count == 22 else 2.80
        pad_size = 1.80 if count == 22 else 2.00
        for i in range(count):
            x = (i - (count - 1) / 2) * pitch
            pads.append(
                f'  (pad "{i+1}" smd roundrect (at {x:.3f} 0) '
                f'(size {pad_size:.2f} {pad_size:.2f}) (layers "F.Cu" "F.Paste" "F.Mask") '
                '(roundrect_rratio 0.20))')
        write(f"EDGE-PADS-{count}", pads)
    # Eleven individual ground lands per side provide one return option for
    # each half of the 22 control wires.  Keeping these rows at the board
    # edges leaves the central signal-routing corridors unobstructed.
    edge_ground = []
    for i in range(11):
        y = (i - 5) * 2.20
        edge_ground.append(
            f'  (pad "{i+1}" smd roundrect (at 0 {y:.3f}) '
            '(size 1.80 1.80) (layers "F.Cu" "F.Paste" "F.Mask") '
            '(roundrect_rratio 0.20))')
    write("GROUND-EDGE-11", edge_ground)
    # Physical user-control interfaces.  Each footprint is an edge-facing
    # group: pad 1 is the outermost GND return, followed inward by its signal
    # pad(s).  Use the same 2 mm SMD land style as the existing edge headers
    # so the bare PCB has one consistent hand-solder pad language.
    def pth(number: int, x: float, y: float) -> str:
        return (f'  (pad "{number}" smd roundrect (at {x:.3f} {y:.3f}) '
                '(size 2.00 2.00) (layers "F.Cu" "F.Paste" "F.Mask") '
                '(roundrect_rratio 0.20))')
    def group(name: str, title: str, pads: list[tuple[str, float, float]],
              width: float, height: float) -> None:
        body = [f'  (fp_rect (start -0.9 -{height/2:.3f}) '
                f'(end {width-0.9:.3f} {height/2:.3f}) '
                '(stroke (width 0.15) (type default)) (fill none) (layer "F.SilkS"))',
                f'  (fp_rect (start -1.0 -{height/2+0.35:.3f}) '
                f'(end {width-0.8:.3f} {height/2+0.35:.3f}) '
                '(stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
                f'  (fp_text user "{title}" (at {(width-1.8)/2:.3f} {-height/2-1.2:.3f}) '
                '(layer "F.SilkS") (effects (font (size 0.75 0.75) (thickness 0.12))))']
        for number, label, x, y in pads:
            body.append(pth(int(number), x, y))
            body.append(f'  (fp_text user "{label}" (at {x:.3f} {y-1.35:.3f}) '
                        '(layer "F.SilkS") (effects (font (size 0.65 0.65) (thickness 0.10))))')
        write(name, body, attr="smd")
    group("MENU-CONTROL-PADS", "LEFT / UI",
          [("1","G",0,-4.5),("2","UP",2.8,-4.5),
           ("3","G",0,-1.5),("4","DN",2.8,-1.5),
           ("5","G",0,1.5),("6","ENT",2.8,1.5),
           ("7","G",0,4.5),("8","BACK",2.8,4.5)], 6.0, 11.0)
    group("ENCODER-CONTROL-PADS", "ENCODER",
          [("1","A",0,-2.0),("2","G",2.8,-2.0),("3","B",5.6,-2.0),
           ("4","PRESS",0,2.0),("5","G",2.8,2.0)], 7.4, 6.0)
    group("ARM-CONTROL-PADS", "ARM",
          [("1","G",0,0),("2","ARM",2.8,0)], 4.6, 2.8)
    for name, title, hi, lo in (("AUX2-CONTROL-PADS","AUX2","AUX2_HI","AUX2_LO"),
                                ("AUX3-CONTROL-PADS","AUX3","AUX3_HI","AUX3_LO"),
                                ("AUX4-CONTROL-PADS","AUX4","AUX4_HI","AUX4_LO")):
        group(name, title, [("1","G",0,0),("2","HI",2.8,0),("3","LO",5.6,0)], 7.4, 2.8)
    for name, title, minus, plus in (("AIL-TRIM-PADS","AIL","AIL-","AIL+"),
                                     ("ELE-TRIM-PADS","ELE","ELE-","ELE+"),
                                     ("THR-TRIM-PADS","THR","THR-","THR+"),
                                     ("RUD-TRIM-PADS","RUD","RUD-","RUD+")):
        group(name, title, [("1","G",0,0),("2",minus,2.8,0),("3",plus,5.6,0)], 7.4, 2.8)
    # Large, hand-solderable ENIG pads for issue #4 developer access.  The
    # two-row arrangement keeps the footprint compact while leaving room for
    # an individual silkscreen label beside each pad.
    dev_pads = []
    for i in range(6):
        x = (i % 3 - 1) * 3.2
        y = -1.8 if i < 3 else 1.8
        dev_pads.append(
            f'  (pad "{i+1}" smd roundrect (at {x:.3f} {y:.3f}) '
            '(size 2.2 1.5) (layers "F.Cu" "F.Paste" "F.Mask") '
            '(roundrect_rratio 0.2))')
    write("DEV-PADS-6", dev_pads)
    dev4_pads = []
    for i in range(4):
        x = (i - 1.5) * 2.8
        dev4_pads.append(
            f'  (pad "{i+1}" smd roundrect (at {x:.3f} 0) '
            '(size 2.2 1.5) (layers "F.Cu" "F.Paste" "F.Mask") '
            '(roundrect_rratio 0.2))')
    write("DEV-PADS-4", dev4_pads)
    write("COAX-SOLDER", [
        '  (pad "1" smd rect (at 0 0) (size 2.5 2) (layers "F.Cu" "F.Mask"))',
        '  (pad "2" smd rect (at -3 0) (size 2.5 3.5) (layers "F.Cu" "F.Mask"))',
        '  (pad "3" smd rect (at 3 0) (size 2.5 3.5) (layers "F.Cu" "F.Mask"))'])
    write("U.FL", [
        '  (fp_rect (start -4 -2.2) (end 4 2.2) (stroke (width 0.05) (type default)) (fill none) (layer "F.Fab"))',
        '  (pad "1" smd rect (at 0 0) (size 2.5 2) (layers "F.Cu" "F.Paste" "F.Mask"))',
        '  (pad "2" smd rect (at -3 0) (size 2.5 3.5) (layers "F.Cu" "F.Paste" "F.Mask"))',
        '  (pad "3" smd rect (at 3 0) (size 2.5 3.5) (layers "F.Cu" "F.Paste" "F.Mask"))'])
    write("SOLDER-JUMPER-3", [
        '  (pad "1" smd rect (at -1 0) (size 0.8 1.5) (layers "F.Cu" "F.Mask"))',
        '  (pad "2" smd rect (at 0 0) (size 0.8 1.5) (layers "F.Cu" "F.Mask"))',
        '  (pad "3" smd rect (at 1 0) (size 0.8 1.5) (layers "F.Cu" "F.Mask"))'])
    write("SOLDER-JUMPER-6", [
        '  (fp_text user "NORMAL" (at -0.5 -2.2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))',
        '  (fp_text user "BYPASS" (at 1.0 2.2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))',
        '  (pad "1" smd rect (at -1 -0.8) (size 0.8 1.0) (layers "F.Cu" "F.Mask"))',
        '  (pad "2" smd rect (at 0 -0.8) (size 0.8 1.0) (layers "F.Cu" "F.Mask"))',
        '  (pad "3" smd rect (at 1 -0.8) (size 0.8 1.0) (layers "F.Cu" "F.Mask"))',
        '  (pad "4" smd rect (at -1 0.8) (size 0.8 1.0) (layers "F.Cu" "F.Mask"))',
        '  (pad "5" smd rect (at 0 0.8) (size 0.8 1.0) (layers "F.Cu" "F.Mask"))',
        '  (pad "6" smd rect (at 1 0.8) (size 0.8 1.0) (layers "F.Cu" "F.Mask"))'])

    lqfp = [
        '  (fp_rect (start -7 -7) (end 7 7) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
        '  (fp_rect (start -8.3 -8.3) (end 8.3 8.3) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
        '  (fp_circle (center -6.2 6.2) (end -5.8 6.2) (stroke (width 0.15) (type default)) (fill solid) (layer "F.SilkS"))']
    coordinates: list[tuple[float, float, float]] = []
    axis = [-3.0 + 0.4 * i for i in range(16)]
    coordinates += [(-7.65, y, 0) for y in reversed(axis)]
    coordinates += [(x, -7.65, 90) for x in axis]
    coordinates += [(7.65, y, 180) for y in axis]
    coordinates += [(x, 7.65, 90) for x in reversed(axis)]
    for pin, (x, y, rotation) in enumerate(coordinates, 1):
        lqfp.append(
            f'  (pad "{pin}" smd rect (at {x:.3f} {y:.3f} {rotation}) '
            '(size 1.3 0.22) (layers "F.Cu" "F.Paste" "F.Mask"))')
    write("LQFP-64_14x14_P0.4", lqfp)

G = "GND"

# Core processors and power path.
esp_gpio = {
    0:"ESP_BOOT",
    1:"GIMBAL_LX",2:"GIMBAL_LY",3:"GIMBAL_RX",4:"GIMBAL_RY",5:"RX_RSSI",
    6:"AUDIO_ENABLE",7:"RX_DATA_MCU",8:"RX_LE_MCU",9:"RX_CLK_MCU",10:"EXP_INT",
    11:"OSD_SCLK_3V3",12:"OSD_MOSI_3V3",13:"OSD_MISO_3V3",14:"OSD_CS_3V3",
    15:"I2C_SDA",16:"I2C_SCL",17:"CRSF_TX_MCU",18:"CRSF_RX_MCU",19:"USB_D-_MCU",
    20:"USB_D+_MCU",21:"OSD_RESET_3V3",26:"AMT_FLASH_CS_ESP",
    33:"AMT_FLASH_CLK_ESP",34:"AMT_FLASH_MOSI_ESP",35:"BUZZER_PWM",
    36:"AMT_FLASH_SEL",37:"AMT_FLASH_MISO_ESP",38:"AMT_RESET",
    39:"AUDIO_I2S_BCLK",40:"SD_CLK_MCU",
    41:"SD_CMD_MCU",42:"SD_D0_MCU",43:"CHARGER_INT",44:"GAUGE_ALERT",
    45:"AUDIO_I2S_WS",46:"AUDIO_I2S_DATA",47:"BACKLIGHT_PWM",48:"VBUS_SENSE"}
_esp_module_order = [
    "GND", "GND", "3V3", "IO0", "IO1", "IO2", "IO3", "IO4", "IO5",
    "IO6", "IO7", "IO8", "IO9", "IO10", "IO11", "IO12", "IO13",
    "IO14", "IO15", "IO16", "IO17", "IO18", "IO19", "IO20", "IO21",
    "IO26", "IO47", "IO33", "IO34", "IO48", "IO35", "IO36", "IO37",
    "IO38", "IO39", "IO40", "IO41", "IO42", "IO43", "IO44", "IO45",
    "GND", "GND", "IO46", "EN"] + ["GND"] * 20
esp_pins=[]
for name in _esp_module_order:
    if name == "3V3": net="3V3_LOGIC"
    elif name == "EN": net="ESP_EN"
    elif name == "GND": net=G
    else: net=esp_gpio.get(int(name[2:]), "NC")
    esp_pins.append((name,net))
add("U1","ESP32-S3-MINI-1U-N8","Espressif","ESP32-S3-MINI-1U-N8",
    "C2980299","ESP32-S3-MINI-1U",esp_pins,16,13)
add("J2","USB-C","GCT","USB4105-GF-A","C3020560","USB4105-GF-A",
    [("GND",G),("VBUS","VBUS_RAW"),("CC2","USB_CC2"),("DP2","USB_D+"),
    ("DN2","USB_D-"),("SBU2","NC"),("VBUS","VBUS_RAW"),("GND",G),
    ("GND",G),("VBUS","VBUS_RAW"),("CC1","USB_CC1"),("DP1","USB_D+"),
    ("DN1","USB_D-"),("SBU1","NC"),("VBUS","VBUS_RAW"),("GND",G),
    ("SHIELD","USB_SHIELD")],5,30,
    pin_numbers=["B1","B4","B5","B6","B7","B8","B9","B12",
                 "A1","A4","A5","A6","A7","A8","A9","A12","1"])
add("ESD1","USB ESD","Texas Instruments","TPD2EUSB30DRTR","C97502",
    "SOT-9X3-3",[("D+","USB_D+"),("D-","USB_D-"),("GND",G)],8,30)
add("F1","USB VBUS resettable fuse","Littelfuse","1206L200PR","C151163",
    "1206",[("1","VBUS_RAW"),("2","VBUS_USB")],9,34)
add("TVS1","USB VBUS TVS","onsemi","ESD5Z5.0T1G","C82044","SOD-523",
    [("K","VBUS_USB"),("A",G)],11,34)

add("U2","1S charger/power path","Texas Instruments","BQ25895RTWR",
    "C80200","WQFN-24-EP",[("VBUS","VBUS_USB"),("D+","NC"),("D-","NC"),
    ("STAT","CHG_STAT"),("SCL","I2C_SCL"),("SDA","I2C_SDA"),
    ("INT","CHARGER_INT"),("OTG",G),("CE",G),("ILIM","CHG_ILIM"),
    ("TS","BAT_NTC"),("QON","CHG_QON"),("BAT","BAT_PROTECTED"),
    ("BAT","BAT_PROTECTED"),("SYS","SYS_ALWAYS"),("SYS","SYS_ALWAYS"),
    ("PGND",G),("PGND",G),("SW","CHG_SW"),("SW","CHG_SW"),
    ("BTST","CHG_BTST"),("REGN","REGN"),("PMID","PMID"),
    ("DSEL","CHG_DSEL"),("EP",G)],14,48)
add("U3","1S protector","Texas Instruments","BQ29700DSER","C183096",
    "WSON-6",[("NC","NC"),("COUT","PROT_COUT"),("DOUT","PROT_DOUT"),
    ("VSS","BAT_CELL_NEG"),("BAT","BAT_SENSE"),("V-","PACK_NEG_SENSE")],4,50)
add("Q1","dual protection FET","FUXINSEMI","FS8205A",
    "C908265","SOT-23-6",[("S1","BAT_CELL_NEG"),("D1D2","BAT_NEG_SENSE"),
    ("S2",G),("G2","PROT_COUT"),("D1D2","BAT_NEG_SENSE"),
    ("G1","PROT_DOUT")],8,53)
add("U4","fuel gauge","Analog Devices","MAX17048G+T10","C2682616",
    "TDFN-8-EP",[("CTG","GAUGE_CTG"),("CELL","GAUGE_CELL"),
    ("VDD","BAT_PROTECTED"),("GND",G),("ALRT","GAUGE_ALERT"),
    ("QSTRT",G),("SCL","I2C_SCL"),("SDA","I2C_SDA"),
    ("EP",G)],20,49)
add("U20","master load switch","Texas Instruments","TPS22992SRXNR",
    "C3229354","WQFN-8",[("VBIAS","SYS_ALWAYS"),("VIN","SYS_ALWAYS"),
    ("PG","POWER_GOOD"),("GND",G),("QOD",G),("VOUT","SYS_SWITCHED"),
    ("CT","MASTER_CT"),("ON","PWR_SW_EN")],27,49)

add("U5","3V3 buck-boost","Texas Instruments","TPS63070RNMR","C109322",
    "VQFN-15",[("PS/SYNC",G),("PG","3V3_PG"),("VAUX","3V3_VAUX"),
    ("GND",G),("FB","3V3_FB"),("FB2",G),("VOUT","3V3_LOGIC"),
    ("VOUT","3V3_LOGIC"),("L2","L3V3_B"),("PGND",G),("L1","L3V3_A"),
    ("VIN","SYS_SWITCHED"),("VIN","SYS_SWITCHED"),("EN","SYS_SWITCHED"),
    ("VSEL",G)],36,49)
add("U6","5V boost","Texas Instruments","TPS61088RHLR","C87357",
    "VQFN-20-EP",[("VCC","5V_VCC"),("EN","SYS_SWITCHED"),
    ("FSW","5V_FSW"),("SW","L5V_SW"),("SW","L5V_SW"),
    ("SW","L5V_SW"),("SW","L5V_SW"),("BOOT","5V_BOOT"),
    ("VIN","SYS_SWITCHED"),("SS","5V_SS"),("NC",G),("NC",G),
    ("MODE",G),("VOUT","SYS_SWITCHED_5V"),("VOUT","SYS_SWITCHED_5V"),
    ("VOUT","SYS_SWITCHED_5V"),("FB","5V_FB"),("COMP","5V_COMP"),
    ("ILIM","5V_ILIM"),("AGND",G),("PGND",G)],47,50)
for index,(ref,net,en,x) in enumerate([
    ("U7","5V_VIDEO","EN_5V_VIDEO",58),("U8","5V_DISPLAY","EN_5V_DISPLAY",65),
    ("U9","5V_ELRS","EN_5V_ELRS",72)]):
    add(ref,net+" load switch","Texas Instruments","TPS22918DBVR","C131941",
        "SOT-23-6",[("VIN","SYS_SWITCHED_5V"),("GND",G),("ON",en),
        ("CT",net+"_CT"),("QOD",G),("VOUT",net)],x,52)
add("U10","display 3V3 buck","Texas Instruments","TPS62162DSGR","C40256",
    "WSON-8-EP",[("PGND",G),("VIN","5V_DISPLAY"),("EN","5V_DISPLAY"),
    ("AGND",G),("FB",G),("VOS","DISPLAY_3V3"),("SW","DISP_SW"),
    ("PG","DISPLAY_3V3_PG"),("EP",G)],78,50)

# Video path and display controller.
rxpins=[("GND",G),("ANT","RX_RF"),("RF_GND",G),("DATA","RX_DATA"),
        ("LE","RX_LE"),("CLK","RX_CLK"),("DGND",G),("5V","5V_VIDEO_FILT"),
        ("RSSI","RX_RSSI_RAW"),("AUDIO","RX_AUDIO_TP"),("VIDEO","VRX_VIDEO_RAW"),
        ("AGND",G)]
add("MOD1","RX5808 SPI receiver","WREKD","RX5808 SPI-modified","C2908157",
    "SMD-12_23.0X28.0X2.54P",rxpins,17,34,"B",notes="pre-order or consigned")
add("U11","analog OSD","Zhongkewei","AT7456E","C82351","TSSOP-28-EP",
    [("NC","NC"),("NC","NC"),("DVDD","5V_VIDEO_FILT"),("DGND",G),
     ("CLKIN","OSD_XTAL_IN"),("XFB","OSD_XTAL_OUT"),("CLKOUT","TP_OSD_CLK"),
     ("CS","OSD_CS_5V"),("SDIN","OSD_MOSI_5V"),("SCLK","OSD_SCLK_5V"),
     ("SDOUT","OSD_MISO_5V"),("LOS","OSD_LOS_5V"),("SYNC_IN","NC"),
     ("NC","NC"),("NC","NC"),("NC","NC"),("VSYNC","TP_OSD_VSYNC"),
     ("HSYNC","TP_OSD_HSYNC"),("RESET","OSD_RESET_5V"),("AGND",G),
     ("AVDD","5V_VIDEO_FILT"),("VIN","VRX_VIDEO_COUPLED"),("PGND",G),
     ("PVDD","5V_VIDEO_FILT"),("SAG","OSD_VIDEO_RAW"),("VOUT","OSD_VIDEO_RAW"),
     ("NC","NC"),("NC","NC"),("EP",G)],35,31)
add("U12","OSD 3V3-to-5V","Texas Instruments","SN74AHCT125PWR","C36365",
    "TSSOP-14",[(str(i+1),n) for i,n in enumerate([
    G,"OSD_SCLK_3V3","OSD_SCLK_5V",G,"OSD_MOSI_3V3","OSD_MOSI_5V",G,
    "OSD_CS_5V","OSD_CS_3V3",G,"OSD_RESET_5V","OSD_RESET_3V3",G,"5V_VIDEO_FILT"])],30,23)
add("U13","OSD 5V-to-3V3","Texas Instruments","SN74LVC1T45DCKR","C9382",
    "SC70-6",[("VCCA","3V3_LOGIC"),("GND",G),("A","OSD_MISO_3V3"),
    ("B","OSD_MISO_5V"),("DIR",G),("VCCB","5V_VIDEO_FILT")],38,22)

amt_nets={1:"AMT_CVBS1",2:"TP_CVBS2",3:"TP_CVBS3",4:"AMT_VCOM",5:G,
10:"DISPLAY_3V3_D",11:"AMT_CORE1",12:G,13:G,14:"AMT_XTAL_OUT",15:"AMT_XTAL_IN",
16:"DISPLAY_3V3_A",17:"AMT_FLASH_CS",18:"AMT_FLASH_MOSI",19:"AMT_FLASH_MISO",
20:"AMT_FLASH_CLK",21:"DISPLAY_3V3_D",22:"AMT_CORE2",23:G,40:"DISPLAY_3V3_D",
41:"AMT_CORE3",42:G,51:"LCD_DCLK_SRC",52:"LCD_DE",53:"LCD_HSYNC",54:"LCD_VSYNC",
55:"TP_AMT_PWM0",56:"TP_AMT_PWM1",57:"TP_AMT_UART0",58:"TP_AMT_UART1",59:"TP_AMT_DIAG",
60:"I2C_SDA",61:"I2C_SCL",62:"DISPLAY_3V3_D",63:"AMT_RESET",64:"DISPLAY_3V3_A"}
for i in range(24,32): amt_nets[i]=f"LCD_R{i-24}"
for i in range(32,40): amt_nets[i]=f"LCD_G{i-32}"
for i in range(43,51): amt_nets[i]=f"LCD_B{i-43}"
for i in range(6,10): amt_nets[i]=f"TP_AMT_P{i}"
add("U14","CVBS TFT controller","Actions Microelectronics","AMT630A",
    "C9900018923","LQFP-64_14x14_P0.4",[(str(i),amt_nets[i]) for i in range(1,65)],52,30)
add("U15","AMT boot flash","Winbond","W25X05CLSNIG","C2641187","SOIC-8",
    [("CS","AMT_FLASH_C"),("MISO","AMT_FLASH_C_MISO"),("WP","DISPLAY_3V3_D"),
    ("GND",G),("MOSI","AMT_FLASH_C_MOSI"),("CLK","AMT_FLASH_C_CLK"),
    ("HOLD","DISPLAY_3V3_D"),("VCC","DISPLAY_3V3_D")],42,17)
add("U16","AMT flash mux","Texas Instruments","SN74CB3Q3257PWR","C397142",
    "TSSOP-16",[("S","AMT_FLASH_SEL"),("1B1","AMT_FLASH_CS"),
    ("1B2","AMT_FLASH_CS_ESP"),("1A","AMT_FLASH_C"),
    ("2B1","AMT_FLASH_CLK"),("2B2","AMT_FLASH_CLK_ESP"),
    ("2A","AMT_FLASH_C_CLK"),("GND",G),("3A","AMT_FLASH_C_MOSI"),
    ("3B2","AMT_FLASH_MOSI_ESP"),("3B1","AMT_FLASH_MOSI"),
    ("4A","AMT_FLASH_C_MISO"),("4B2","AMT_FLASH_MISO_ESP"),
    ("4B1","AMT_FLASH_MISO"),("OE",G),("VCC","DISPLAY_3V3_D")],48,16)

ffc=[("LEDK","BL_LED_K"),("LEDA","BL_LED_A"),("GND",G),("VDD","PANEL_3V3")]
ffc += [(f"R{i}",f"LCD_R{i}") for i in range(8)]
ffc += [(f"G{i}",f"LCD_G{i}") for i in range(8)]
ffc += [(f"B{i}",f"LCD_B{i}") for i in range(8)]
ffc += [("GND",G),("CLK","LCD_DCLK"),("DISP","LCD_DISP"),("HSYNC","LCD_HSYNC"),
        ("VSYNC","LCD_VSYNC"),("DEN","LCD_DE"),("NC","NC"),("GND",G),
        ("NC37","NC"),("NC38","NC"),("NC39","NC"),("NC40","NC")]
add("J1","ER-TFT050A3-2 FFC","Hirose","FH12-40S-0.5SH(55)","C202114",
    "FH12-40S-0.5SH(55)",ffc,67.5,30)

# Backlight, controls, buzzer, and future speaker.
add("U17","backlight boost","Texas Instruments","TPS61165DRVR","C122568",
    "WSON-6-EP",[("FB","BL_LED_K"),("COMP","BL_COMP"),("GND",G),
    ("SW","BL_SW"),("CTRL","BACKLIGHT_PWM"),("VIN","5V_DISPLAY"),
    ("EP",G)],79,32)
for ref,addr,x in [("U18","0x20",67),("U19","0x21",75)]:
    if ref == "U18":
        port_nets = [f"CTRL_0_{i}" for i in range(16)]
    else:
        port_nets = [f"CTRL_1_{i}" for i in range(6)] + [
            "SD_CARD_DETECT", "EN_3V3_SD", "EN_5V_VIDEO",
            "EN_5V_DISPLAY", "EN_5V_ELRS", "LCD_DISP",
            "DEV_IO0", "DEV_IO1", "DEV_IO2", "DEV_IO3"]
    pins=[("INT","EXP_INT"),("A1",G),("A2",G)]
    pins += [(f"P0{i}",port_nets[i]) for i in range(8)]
    pins += [("GND",G)]
    pins += [(f"P1{i}",port_nets[i+8]) for i in range(8)]
    pins += [("A0",G if addr=="0x20" else "3V3_LOGIC"),
             ("SCL","I2C_SCL"),("SDA","I2C_SDA"),("VCC","3V3_LOGIC")]
    add(ref,"GPIO expander "+addr,"Texas Instruments","TCA9535PWR","C130204",
        "TSSOP-24",pins,x,12)
add("BZ1","passive magnetic buzzer","Fengming","YS-SBZ7525C05R30","C7421675",
    "SMD-7.5x7.5",[("+","BUZZER_5V"),("-","BUZZER_LOW")],84,9)
add("Q2","Q_BUZZ buzzer MOSFET","Alpha & Omega","AO3400A","C20917","SOT-23",
    [("G","BUZZER_GATE"),("S",G),("D","BUZZER_LOW")],84,5)
add("D2","D_BUZZ buzzer flyback","LGE","1N4148W","C81598","SOD-123",
    [("K","BUZZER_5V"),("A","BUZZER_LOW")],82,14)
add("U21","I2S speaker amplifier","Nsiway","NS4168","C910588","ESOP-8-EP",
    [("CTRL","AUDIO_ENABLE"),("LRCLK","AUDIO_I2S_WS"),
    ("BCLK","AUDIO_I2S_BCLK"),("SDATA","AUDIO_I2S_DATA"),
    ("VON","SPK-"),("VDD","SYS_SWITCHED_5V"),("GND",G),
    ("VOP","SPK+"),("EP",G)],80,22)
add("J4","speaker connector","JST","S2B-PH-SM4-TB(LF)(SN)","C295747",
    "JST-PH-2-SMD",[("SPK+","SPK+"),("SPK-","SPK-")],87,22)
add("J13","speaker solder pads","OpenPocket","SOLDER-PADS-2","CONS",
    "EDGE-PADS-2",[("SPK+","SPK+"),("SPK-","SPK-")],86,26,
    dnp=True,notes="integral differential speaker pads; neither pad is ground")
# Issue #4 developer access pads.  The OLED shares the existing ESP32 I2C
# bus; DEV_IO0..3 are the previously unused U19/TCA9535 port pins.
add("J14","SSD1306 128x64 OLED pads","OpenPocket","DEV-PADS-4","CONS",
    "DEV-PADS-4",[("GND","GND"),("VCC","3V3_LOGIC"),
                   ("SDA","I2C_SDA"),("SCL","I2C_SCL")],101,18,
    dnp=True,notes="four-wire SSD1306/SH1106 128x64 OLED; shared GPIO15/GPIO16 I2C bus")
add("J15","expander developer pads","OpenPocket","DEV-PADS-6","CONS",
    "DEV-PADS-6",[("IO0","DEV_IO0"),("IO1","DEV_IO1"),
                   ("IO2","DEV_IO2"),("IO3","DEV_IO3"),
                   ("3V3","3V3_LOGIC"),("GND","GND")],101,56,
    dnp=True,notes="hand-solder TCA9535 U19 slow-I/O access")

# Dedicated 1-bit SDMMC removable storage. The socket's normally-open card
# switch closes SD_CARD_DETECT to ground when a card is fully inserted.
add("U22","3V3_SD load switch","Texas Instruments","TPS22918DBVR","C131941",
    "SOT-23-6",[("VIN","3V3_LOGIC"),("GND",G),("ON","EN_3V3_SD"),
    ("CT","3V3_SD_CT"),("QOD",G),("VOUT","3V3_SD")],24,8)
sd_socket_pins=[("DAT2","SD_DAT2"),("DAT3","SD_DAT3"),("CMD","SD_CMD"),
    ("VDD","3V3_SD"),("CLK","SD_CLK"),("VSS",G),("DAT0","SD_D0"),
    ("DAT1","SD_DAT1"),("CD","SD_CARD_DETECT")]+[("SH",G)]*4
add("J12","push-push microSD","SOFNG","TF-001A-P3","C3021282",
    "TF-001A-P3",sd_socket_pins,32,8,
    notes="card detect active-low; card ejects toward top edge")
add("ESD2","microSD ESD array A","Texas Instruments","TPD4E001DRLR",
    "C527516","SOT-563",[("IO1","SD_CLK"),("IO2","SD_CMD"),("GND",G),
    ("IO3","SD_D0"),("IO4","SD_DAT1"),("VCC","3V3_SD")],39,7)
add("ESD3","microSD ESD array B","Texas Instruments","TPD4E001DRLR",
    "C527516","SOT-563",[("IO1","SD_DAT2"),("IO2","SD_DAT3"),("GND",G),
    ("IO3","NC"),("IO4","NC"),("VCC","3V3_SD")],39,9)
for ref,net,x,y in [
    ("TP1","3V3_SD",27,12),("TP2","SD_CLK",29,12),
    ("TP3","SD_CMD",31,12),("TP4","SD_D0",33,12),
    ("TP5","SD_CARD_DETECT",35,12),("TP6",G,37,12)]:
    add(ref,net+" test pad","OpenPocket","PCB-TEST-PAD-1.0MM","N/A",
        "TEST-PAD-1.0MM",[("1",net)],x,y,dnp=True,
        notes="bare ENIG copper test feature; not an assembled component")

# External/user interfaces.
add("J3","battery/NTC","OpenPocket","SOLDER-PADS-4","CONS","EDGE-PADS-4",
    [("BAT+","BAT_RAW"),("BAT-","BAT_CELL_NEG"),("NTC","BAT_NTC"),("NTC_GND",G)],4,56,
    dnp=True,notes="integral solder pads; user-wired, not an assembly item")
add("J5","master switch","OpenPocket","SOLDER-PADS-2","CONS","EDGE-PADS-2",
    [("PWR_SW_A","SYS_ALWAYS"),("PWR_SW_B","PWR_SW_EN")],24,56,
    dnp=True,notes="integral solder pads; user-wired, not an assembly item")
add("J6","ELRS","OpenPocket","SOLDER-PADS-4","CONS","EDGE-PADS-4",
    [("5V","5V_ELRS"),("GND",G),("RX","CRSF_TX"),("TX","CRSF_RX")],61,56,
    dnp=True,notes="four-wire ELRS UART/power pads; BOOT and RESET remain internal debug nets")
add("ESD4","ELRS UART ESD","Texas Instruments","TPD2EUSB30DRTR","C97502",
    "SOT-9X3-3",[("TX","CRSF_TX"),("RX","CRSF_RX"),("GND",G)],73,56)
add("J7","left gimbal","OpenPocket","SOLDER-PADS-6","CONS","EDGE-PADS-6",
    [("LX","GIMBAL_LX_RAW"),("LX_VCC","3V3_LOGIC"),("LX_GND",G),
     ("LY","GIMBAL_LY_RAW"),("LY_VCC","3V3_LOGIC"),("LY_GND",G)],78,56,
    dnp=True,notes="integral solder pads; user-wired, not an assembly item")
add("J8","right gimbal","OpenPocket","SOLDER-PADS-6","CONS","EDGE-PADS-6",
    [("RX","GIMBAL_RX_RAW"),("RX_VCC","3V3_LOGIC"),("RX_GND",G),
     ("RY","GIMBAL_RY_RAW"),("RY_VCC","3V3_LOGIC"),("RY_GND",G)],87,55,
    dnp=True,notes="integral solder pads; user-wired, not an assembly item")
add("J9","menu/UI control pads","OpenPocket","MENU-CONTROL-PADS","CONS","MENU-CONTROL-PADS",
    [("G_UP",G),("MENU_UP","CTRL_0_0"),("G_DN",G),("MENU_DOWN","CTRL_0_1"),
     ("G_ENT",G),("MENU_ENTER","CTRL_0_2"),("G_BACK",G),("MENU_BACK","CTRL_0_3")],4,10,
    dnp=True,notes="left-edge menu pads; each button has adjacent edge-side GND")
add("J18","rotary encoder control pads","OpenPocket","ENCODER-CONTROL-PADS","CONS","ENCODER-CONTROL-PADS",
    [("ENC_A","CTRL_1_4"),("G_ENC_A",G),("ENC_B","CTRL_1_5"),
     ("ENC_PRESS","CTRL_0_11"),("G_ENC_PRESS",G)],4,48,
    dnp=True,notes="left-edge encoder A/G/B plus press/G pads")
add("J19","ARM switch pads","OpenPocket","ARM-CONTROL-PADS","CONS","ARM-CONTROL-PADS",
    [("G_ARM",G),("ARM","CTRL_0_4")],111,10,"F",True,
    notes="right-edge ARM switch; GND is the outermost pad",rotation=180)
for ref, title, hi, lo, y, hi_net, lo_net in (("J20","AUX2","AUX2_HI","AUX2_LO",28,5,6),
                                               ("J21","AUX3","AUX3_HI","AUX3_LO",32,7,8),
                                               ("J22","AUX4","AUX4_HI","AUX4_LO",46,9,10)):
    add(ref,f"{title} three-position switch pads","OpenPocket",f"{title}-CONTROL-PADS","CONS",f"AUX{title[-1]}-CONTROL-PADS",
        [("G",G),("HI",f"CTRL_0_{hi_net}"),("LO",f"CTRL_0_{lo_net}")],111,y,"F",True,
        notes=f"right-edge {title} group; edge-side GND between the signal escape points",rotation=180)
for ref, title, minus, plus, n, side in (("J23","AIL","AIL-","AIL+",50,"F"),
                                         ("J24","ELE","ELE-","ELE+",60,"F"),
                                         ("J25","THR","THR-","THR+",34,"F"),
                                         ("J26","RUD","RUD-","RUD+",44,"F")):
    net_minus = {"AIL-":"CTRL_0_12","ELE-":"CTRL_0_14","THR-":"CTRL_1_0","RUD-":"CTRL_1_2"}[minus]
    net_plus = {"AIL+":"CTRL_0_13","ELE+":"CTRL_0_15","THR+":"CTRL_1_1","RUD+":"CTRL_1_3"}[plus]
    add(ref,f"{title} trim pads","OpenPocket",f"{title}-TRIM-PADS","CONS",f"{title}-TRIM-PADS",
        [("G",G),("MINUS",net_minus),("PLUS",net_plus)],111,n,side,True,
        notes=f"{title} three-wire trim group with adjacent edge-side GND",
        rotation=0 if ref in {"J25", "J26"} else 180)
add("J11","5.8 GHz antenna U.FL","Hirose","U.FL-R-SMT-1(10)","C88373","U.FL",
    [("RF","RX_RF"),("GND",G),("GND",G)],5,16,
    notes="populate on bottom; accepts U.FL/MHF1 plug vertically; secure cable to enclosure")

# Passives. Exact MPN families are frozen; the supplier column identifies JLC.
def passive(ref,value,mpn,lcsc,package,n1,n2,x,y,dnp=False):
    manufacturer=("Yageo" if mpn.startswith(("RC", "CC")) else
                  "Samsung Electro-Mechanics" if mpn.startswith("CL") else
                  "HRE" if mpn.startswith("CGA") else
                  "Panasonic" if mpn.startswith("EEE") else
                  "Lelon" if mpn.startswith("VZH") else
                  "Fenghua Advanced" if mpn.startswith("0603B") else
                  "Uniroyal Electronics")
    add(ref,value,manufacturer,
        mpn,lcsc,package,[("1",n1),("2",n2)],x,y,dnp=dnp)

resistors=[
 ("R1","5.1k","RC0402FR-075K1L","C105872","USB_CC1",G),
 ("R2","5.1k","RC0402FR-075K1L","C105872","USB_CC2",G),
 ("R3","10k","RC0402FR-0710KL","C60490","ESP_EN","3V3_LOGIC"),
 ("R4","10k","RC0402FR-0710KL","C60490","PWR_SW_EN",G),
 ("R5","100k","RC0402FR-07100KL","C60491","AMT_FLASH_SEL",G),
 ("R6","100","RC0402FR-07100RL","C106232","BUZZER_PWM","BUZZER_GATE"),
 ("R7","100k","RC0402FR-07100KL","C60491","BUZZER_GATE",G),
 ("R8","100k","RC0402FR-07100KL","C60491","AUDIO_ENABLE",G),
 ("R9","4.99","RC0603FR-074R99L","C137704","BL_LED_K",G),
 ("R10","18","RC0603FR-0718RL","C245924","OSD_VIDEO_BYP","AMT_CVBS_PRE"),
 ("R11","56","RC0603FR-0756RL","C126360","AMT_CVBS1",G),
 ("R12","100k","RC0402FR-07100KL","C60491","OSD_CS_5V","5V_VIDEO_FILT"),
 ("R13","100k","RC0402FR-07100KL","C60491","AMT_RESET","DISPLAY_3V3_D"),
 ("R14","2.2k","RC0402FR-072K2L","C114762","I2C_SDA","3V3_LOGIC"),
 ("R15","2.2k","RC0402FR-072K2L","C114762","I2C_SCL","3V3_LOGIC"),
 ("R16","100k","RC0402FR-07100KL","C60491","AUDIO_ENABLE",G),
 ("R18","1M","RC0402FR-071ML","C138033","AMT_XTAL_OUT","AMT_XTAL_IN"),
 ("R20","316k","RC0402FR-07316KL","C185427","SYS_SWITCHED_5V","5V_FB"),
 ("R21","100k","RC0402FR-07100KL","C60491","5V_FB",G),
 ("R22","1M","RC0402FR-071ML","C138033","3V3_LOGIC","3V3_FB"),
 ("R23","316k","RC0402FR-07316KL","C185427","3V3_FB",G),
 ("R24","150k","RC0402FR-07150KL","C93947","5V_ILIM",G),
 ("R25","1k","RC0402FR-071KL","C106235","RX_RSSI_RAW","RX_RSSI_FILT"),
 ("R26","12k","RC0402FR-0712KL","C114760","RX_RSSI_FILT","RX_RSSI"),
 ("R27","18k","RC0402FR-0718KL","C138044","RX_RSSI",G),
 ("R28","27","RC0402FR-0727RL","C138021","USB_D-_MCU","USB_D-"),
 ("R29","27","RC0402FR-0727RL","C138021","USB_D+_MCU","USB_D+"),
 ("R30","10k","RC0402FR-0710KL","C60490","SD_CMD","3V3_SD"),
 ("R31","10k","RC0402FR-0710KL","C60490","SD_D0","3V3_SD"),
 ("R32","10k","RC0402FR-0710KL","C60490","SD_DAT1","3V3_SD"),
 ("R33","10k","RC0402FR-0710KL","C60490","SD_DAT2","3V3_SD"),
 ("R34","10k","RC0402FR-0710KL","C60490","SD_DAT3","3V3_SD"),
 ("R35","10k","RC0402FR-0710KL","C60490","SD_CARD_DETECT","3V3_LOGIC"),
 ("R36","100k","RC0402FR-07100KL","C60491","EN_3V3_SD",G),
 ("R37","27","RC0402FR-0727RL","C138021","SD_CLK_MCU","SD_CLK"),
 ("R38","27","RC0402FR-0727RL","C138021","SD_CMD_MCU","SD_CMD"),
 ("R39","27","RC0402FR-0727RL","C138021","SD_D0_MCU","SD_D0"),
 ("R40","100k","RC0402FR-07100KL","C60491","VBUS_USB","VBUS_SENSE"),
 ("R41","100k","RC0402FR-07100KL","C60491","VBUS_SENSE",G),
 ("R42","750","RC0402FR-07750RL","C137936","CHG_ILIM",G),
 ("R43","10k","RC0402FR-0710KL","C60490","CHG_STAT","REGN"),
 ("R44","10k","RC0402FR-0710KL","C60490","CHG_QON","REGN"),
 ("R45","10k","RC0402FR-0710KL","C60490","CHG_DSEL","REGN"),
 ("R46","5.23k","RC0402FR-075K23L","C477746","REGN","BAT_NTC"),
 ("R47","30.1k","RC0402FR-0730K1L","C138009","BAT_NTC",G),
 ("R48","10k","RC0402FR-0710KL","C60490","POWER_GOOD","3V3_LOGIC"),
 ("R49","10k","RC0402FR-0710KL","C60490","3V3_PG","3V3_LOGIC"),
 ("R50","10k","RC0402FR-0710KL","C60490","DISPLAY_3V3_PG","3V3_LOGIC"),
 ("R51","330k","RC0402FR-07330KL","C138006","L5V_SW","5V_FSW"),
 ("R52","18.2k","RC0402FR-0718K2L","C274351","5V_COMP","5V_COMP_RC"),
 ("R53","1k","RC0402FR-071KL","C106235","OSD_LOS_5V","5V_VIDEO_FILT"),
 ("R54","1M","RC0402FR-071ML","C138033","USB_SHIELD",G),
 ("R55","10","RC0402FR-0710RL","C138066","BAT_PROTECTED","GAUGE_CELL"),
 ("R56","330","0402WGF3300TCE","C25104","BAT_RAW","BAT_SENSE"),
 ("R57","2.2k","0402WGF2201TCE","C25879",G,"PACK_NEG_SENSE"),
 ("R58","33","RC0402FR-0733RL","C138002","LCD_DCLK_SRC","LCD_DCLK"),
 ("R59","33","RC0402FR-0733RL","C138002","RX_DATA_MCU","RX_DATA"),
 ("R60","33","RC0402FR-0733RL","C138002","RX_LE_MCU","RX_LE"),
 ("R61","33","RC0402FR-0733RL","C138002","RX_CLK_MCU","RX_CLK"),
 ("R62","5.1M","0402WGF5104TCE","C270595","PROT_DOUT","BAT_CELL_NEG"),
 ("R63","5.1M","0402WGF5104TCE","C270595","PROT_COUT",G),
 ("R64","1k","RC0402FR-071KL","C106235","TP_OSD_HSYNC","5V_VIDEO_FILT"),
 ("R65","1k","RC0402FR-071KL","C106235","TP_OSD_VSYNC","5V_VIDEO_FILT"),
 ("R66","100k","RC0402FR-07100KL","C60491","OSD_CS_3V3","3V3_LOGIC"),
 ("R67","100k","RC0402FR-07100KL","C60491","OSD_RESET_3V3",G),
 ("R68","100k","RC0402FR-07100KL","C60491","OSD_SCLK_3V3",G),
 ("R69","100k","RC0402FR-07100KL","C60491","OSD_MOSI_3V3",G),
 ("R70","10k","RC0402FR-0710KL","C60490","EXP_INT","3V3_LOGIC"),
 ("R71","10k","RC0402FR-0710KL","C60490","CHARGER_INT","3V3_LOGIC"),
 ("R72","10k","RC0402FR-0710KL","C60490","GAUGE_ALERT","3V3_LOGIC"),
]
for index in range(16):
    resistors.append((f"R{73+index}","10k","RC0402FR-0710KL","C60490",
                      f"CTRL_0_{index}","3V3_LOGIC"))
for index in range(6):
    resistors.append((f"R{89+index}","10k","RC0402FR-0710KL","C60490",
                      f"CTRL_1_{index}","3V3_LOGIC"))
resistors += [
 ("R95","1k","RC0402FR-071KL","C106235","GIMBAL_LX_RAW","GIMBAL_LX"),
 ("R96","1k","RC0402FR-071KL","C106235","GIMBAL_LY_RAW","GIMBAL_LY"),
 ("R97","1k","RC0402FR-071KL","C106235","GIMBAL_RX_RAW","GIMBAL_RX"),
 ("R98","1k","RC0402FR-071KL","C106235","GIMBAL_RY_RAW","GIMBAL_RY"),
 ("R99","33","RC0402FR-0733RL","C138002","CRSF_TX_MCU","CRSF_TX"),
 ("R100","33","RC0402FR-0733RL","C138002","CRSF_RX","CRSF_RX_MCU"),
 ("R101","0","RC0402FR-070RL","C106231","SYS_SWITCHED_5V","BUZZER_5V"),
 ("R102","100","RC0402FR-07100RL","C106232","BUZZER_LOW","BUZZER_SNUB"),
]
sd_resistor_positions={
    "R30":(35.0,5.0),"R31":(35.0,5.8),"R32":(35.0,6.6),
    "R33":(35.0,7.4),"R34":(35.0,8.2),"R35":(35.0,9.0),
    "R36":(24.0,10.0),"R37":(23.0,5.5),"R38":(23.0,6.3),
    "R39":(23.0,7.1)}
for i,row in enumerate(resistors):
    x,y=sd_resistor_positions.get(row[0],(28+(i%12)*2.3,5+(i//12)*2.2))
    passive(row[0],row[1],row[2],row[3],"0402",row[4],row[5],
            x,y,dnp=row[0] == "R102")
passive("R103","75","RC0603FR-0775RL","C112309","0603",
        "VRX_VIDEO_TO_OSD",G,38,30)
passive("R104","10k","RC0402FR-0710KL","C60490","0402",
        "ESP_BOOT","3V3_LOGIC",18,18)

caps=[
 ("C1","100n","CL05B104KO5NNNC","C1525","0402","3V3_LOGIC",G),
 ("C2","10u","CL21A106KAYNNNE","C15850","0805","SYS_ALWAYS",G),
 ("C3","10u","CL21A106KAYNNNE","C15850","0805","SYS_SWITCHED",G),
 ("C4","100n","CL05B104KO5NNNC","C1525","0402","5V_VIDEO_FILT",G),
 ("C5","10u","CL21A106KAYNNNE","C15850","0805","5V_VIDEO_FILT",G),
 ("C6","470u","VZH471M1ATR-1008","C249929","SMD-D10","5V_VIDEO_FILT",G),
 ("C7","100n","CL05B104KO5NNNC","C1525","0402","VRX_VIDEO_TO_OSD","VRX_VIDEO_COUPLED"),
 ("C8","22n","CL05B223KB5NNNC","C337699","0402","AMT_CVBS_PRE","AMT_CVBS1"),
 ("C9","100n","CL05B104KO5NNNC","C1525","0402","DISPLAY_3V3_D",G),
 ("C10","4.7u","CL10A475KP8NNNC","C1705","0603","AMT_CORE1",G),
 ("C11","4.7u","CL10A475KP8NNNC","C1705","0603","AMT_CORE2",G),
 ("C12","4.7u","CL10A475KP8NNNC","C1705","0603","AMT_CORE3",G),
 ("C15","33p C0G","CC0402JRNPO9BN330","C107005","0402","AMT_XTAL_OUT",G),
 ("C16","33p C0G","CC0402JRNPO9BN330","C107005","0402","AMT_XTAL_IN",G),
 ("C17","100n","CL05B104KO5NNNC","C1525","0402","SYS_SWITCHED_5V",G),
 ("C18","10u","CL21A106KAYNNNE","C15850","0805","SYS_SWITCHED_5V",G),
 ("C19","10u","CL21A106KAYNNNE","C15850","0805","DISPLAY_3V3",G),
 ("C20","100n","CL05B104KO5NNNC","C1525","0402","AUDIO_ENABLE",G),
 ("C21","10u","CL21A106KAYNNNE","C15850","0805","SYS_SWITCHED_5V",G),
 ("C22","100n","CL05B104KO5NNNC","C1525","0402","RX_RSSI",G),
 ("C23","10n","CL05B103KB5NNNC","C15195","0402","MASTER_CT",G),
 ("C24","100n","CL05B104KO5NNNC","C1525","0402","3V3_SD",G),
 ("C25","10u","CL21A106KAYNNNE","C15850","0805","3V3_SD",G),
 ("C26","47u","CL31A476MPHNNNE","C96123","1206","3V3_SD",G),
 ("C27","1n","CL05B102KB5NNNC","C14442","0402","3V3_SD_CT",G),
 ("C28","10u 25V","CGA0805X7R106K250MT","C6119932","0805","PMID",G),
 ("C29","4.7u 10V","0603B475K100NT","C108342","0603","REGN",G),
 ("C30","47n 50V","CC0402KRX7R9BB473","C272875","0402","CHG_BTST","CHG_SW"),
 ("C31","10u 25V","CGA0805X7R106K250MT","C6119932","0805","BAT_PROTECTED",G),
 ("C32","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_ALWAYS",G),
 ("C33","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_ALWAYS",G),
 ("C34","10u 25V","CGA0805X7R106K250MT","C6119932","0805","VBUS_USB",G),
 ("C35","100n","CL05B104KO5NNNC","C1525","0402","3V3_VAUX",G),
 ("C36","10u","CL21A106KAYNNNE","C15850","0805","SYS_SWITCHED",G),
 ("C37","10u","CL21A106KAYNNNE","C15850","0805","SYS_SWITCHED",G),
 ("C38","22u 10V","CGA0805X7R226M100MT","C23692981","0805","3V3_LOGIC",G),
 ("C39","22u 10V","CGA0805X7R226M100MT","C23692981","0805","3V3_LOGIC",G),
 ("C40","2.2u","CL10A225KO8NNNC","C23630","0603","5V_VCC",G),
 ("C41","100n","CL05B104KO5NNNC","C1525","0402","5V_BOOT","L5V_SW"),
 ("C42","47n 50V","CC0402KRX7R9BB473","C272875","0402","5V_SS",G),
 ("C43","4.7n","CL05B472KB5NNNC","C84705","0402","5V_COMP_RC",G),
 ("C44","2.2n","CL05B222KB5NNNC","C84703","0402","5V_COMP",G),
 ("C45","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_SWITCHED",G),
 ("C46","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_SWITCHED",G),
 ("C47","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_SWITCHED_5V",G),
 ("C48","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_SWITCHED_5V",G),
 ("C49","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_SWITCHED_5V",G),
 ("C50","22u 10V","CGA0805X7R226M100MT","C23692981","0805","SYS_SWITCHED_5V",G),
 ("C51","10u","CL21A106KAYNNNE","C15850","0805","5V_DISPLAY",G),
 ("C52","22u 10V","CGA0805X7R226M100MT","C23692981","0805","DISPLAY_3V3",G),
 ("C53","4.7u 10V","0603B475K100NT","C108342","0603","5V_DISPLAY",G),
 ("C54","220n","CC0402KRX7R8BB224","C723566","0402","BL_COMP",G),
 ("C55","1u 50V","CC0805KKX7R9BB105","C91185","0805","BL_LED_A",G),
 ("C56","1u 50V","CC0805KKX7R9BB105","C91185","0805","BL_LED_A",G),
 ("C57","100n","CL05B104KO5NNNC","C1525","0402","5V_VIDEO_FILT",G),
 ("C58","100n","CL05B104KO5NNNC","C1525","0402","5V_VIDEO_FILT",G),
 ("C59","100n","CL05B104KO5NNNC","C1525","0402","5V_VIDEO_FILT",G),
 ("C60","10u","CL21A106KAYNNNE","C15850","0805","5V_VIDEO_FILT",G),
 ("C61","470n 16V","CGA0402X7R474K160GT","C22435970","0402","GAUGE_CTG",G),
 ("C62","100n","CL05B104KO5NNNC","C1525","0402","GAUGE_CELL",G),
 ("C63","4.7n","CL05B472KB5NNNC","C84705","0402","USB_SHIELD",G),
 ("C64","1n","CL05B102KB5NNNC","C14442","0402","5V_VIDEO_CT",G),
 ("C65","1n","CL05B102KB5NNNC","C14442","0402","5V_DISPLAY_CT",G),
 ("C66","1n","CL05B102KB5NNNC","C14442","0402","5V_ELRS_CT",G),
 ("C67","100n","CL05B104KO5NNNC","C1525","0402","BAT_SENSE","BAT_CELL_NEG"),
 ("C68","1u","CL05A105KA5NQNC","C52923","0402","AMT_VCOM",G),
 ("C69","100n","CL05B104KO5NNNC","C1525","0402","DISPLAY_3V3_A",G),
 ("C70","100n","CL05B104KO5NNNC","C1525","0402","DISPLAY_3V3_D",G),
 ("C71","100n","CL05B104KO5NNNC","C1525","0402","DISPLAY_3V3_D",G),
 ("C72","100n","CL05B104KO5NNNC","C1525","0402","DISPLAY_3V3_D",G),
 ("C73","100n","CL05B104KO5NNNC","C1525","0402","DISPLAY_3V3_A",G),
 ("C74","100n","CL05B104KO5NNNC","C1525","0402","5V_ELRS",G),
 ("C75","10u","CL21A106KAYNNNE","C15850","0805","5V_ELRS",G),
 ("C77","100n","CL05B104KO5NNNC","C1525","0402","SYS_SWITCHED_5V",G),
 ("C78","100n","CL05B104KO5NNNC","C1525","0402","GIMBAL_LX",G),
 ("C79","100n","CL05B104KO5NNNC","C1525","0402","GIMBAL_LY",G),
 ("C80","100n","CL05B104KO5NNNC","C1525","0402","GIMBAL_RX",G),
 ("C81","100n","CL05B104KO5NNNC","C1525","0402","GIMBAL_RY",G),
 ("C82","100n","CL05B104KO5NNNC","C1525","0402","BUZZER_5V",G),
]
sd_cap_positions={"C24":(28.0,10.0),"C25":(29.5,10.0),
                  "C26":(31.5,10.0),"C27":(24.8,9.2)}
for i,(ref,val,mpn,lcsc,pkg,n1,n2) in enumerate(caps):
    x,y=sd_cap_positions.get(ref,(56+(i%12)*2.2,5+(i//12)*2.1))
    passive(ref,val,mpn,lcsc,pkg,n1,n2,x,y)
passive("C76","220u 10V","EEEFK1A221P","C401648","SMD-D8",
        "5V_ELRS",G,70,48,dnp=True)
passive("C83","10n","CL05B103KB5NNNC","C15195","0402",
        "BUZZER_SNUB","BUZZER_5V",81,7,dnp=True)

add("Y1","27.000MHz","Abracon","ABM8-27.000MHZ-B2-T","C1985251","ABM8",
    [("1","OSD_XTAL_OUT"),("2",G),("3","OSD_XTAL_IN"),("4",G)],37,37)
add("Y2","27.000MHz","Abracon","ABM8-27.000MHZ-B2-T","C1985251","ABM8",
    [("1","AMT_XTAL_OUT"),("2",G),("3","AMT_XTAL_IN"),("4",G)],45,38)
add("L1","2.2uH charger","Sunlord","SWPA4030S2R2MT","C36409",
    "L-4x4",[("1","CHG_SW"),("2","SYS_ALWAYS")],20,53)
add("L2","1uH 3V3","Sunlord","SWPA4020S1R0MT","C142484","L-4x4",
    [("1","L3V3_A"),("2","L3V3_B")],39,54)
add("L3","1.8uH 5V 10A","Coilcraft","XAL6030-182MEC","C19191693","L-6.5x6.3",
    [("1","SYS_SWITCHED"),("2","L5V_SW")],51,55)
add("L4","10uH backlight","Sunlord","SWPA4020S100MT","C82398","L-4x4",
    [("1","5V_DISPLAY"),("2","BL_SW")],82,36)
add("L5","2.2uH display buck","Sunlord","SWPA3015S2R2MT","C43389","L-3x3",
    [("1","DISP_SW"),("2","DISPLAY_3V3")],76,46)
add("D1","40V Schottky","Diodes Inc","B240A-13-F","C92506","SMA",
    [("K","BL_LED_A"),("A","BL_SW")],85,36)
add("FB1","video ferrite","Murata","BLM21PG221SN1D","C85840","0805",
    [("1","5V_VIDEO"),("2","5V_VIDEO_FILT")],26,38)
add("FB2","AMT analog ferrite","Murata","BLM18AG601SN1D","C19330","0603",
    [("1","DISPLAY_3V3"),("2","DISPLAY_3V3_A")],48,42)
add("FB3","AMT digital ferrite","Murata","BLM18AG601SN1D","C19330","0603",
    [("1","DISPLAY_3V3"),("2","DISPLAY_3V3_D")],51,42)
add("FB4","panel logic ferrite","Murata","BLM18AG601SN1D","C19330","0603",
    [("1","DISPLAY_3V3"),("2","PANEL_3V3")],55,42)

# Two-pole diagnostic selector. Factory NORMAL bridges 1-2 and 4-5. To use
# BYPASS, remove both NORMAL bridges and bridge only 5-6. The first pole then
# disconnects the AT7456E input termination while the second routes RX video
# directly to the AMT630A, so the two video-driver outputs can never meet.
add("JP1","CVBS NORMAL/BYPASS","OpenPocket","SJ-DPDT","N/A","SOLDER-JUMPER-6",
    [("OSD_IN","VRX_VIDEO_TO_OSD"),("RX_COMMON","VRX_VIDEO_RAW"),("OPEN","NC"),
     ("OSD_OUT","OSD_VIDEO_RAW"),("AMT_COMMON","OSD_VIDEO_BYP"),
     ("RX_BYPASS","VRX_VIDEO_RAW")],41,31,dnp=True,
    notes="factory hand-bridge pads 1-2 and 4-5; bypass cuts both and bridges 5-6")

# Bare ENIG diagnostics are real PCB features, not assembly items.  Besides
# factory access, they keep every intentionally exposed one-pin net explicit
# in ERC rather than suppressing connectivity diagnostics.
diagnostic_nets = [
    "TP_CVBS2", "TP_CVBS3", "TP_AMT_P6", "TP_AMT_P7", "TP_AMT_P8",
    "TP_AMT_P9", "TP_AMT_DIAG", "TP_AMT_UART1", "TP_AMT_UART0",
    "TP_AMT_PWM1", "TP_AMT_PWM0", "RX_AUDIO_TP", "TP_OSD_CLK",
    "TP_OSD_HSYNC", "TP_OSD_VSYNC",
    "SYS_ALWAYS", "SYS_SWITCHED", "POWER_GOOD", "3V3_LOGIC",
    "SYS_SWITCHED_5V", "5V_VIDEO", "5V_DISPLAY", "5V_ELRS",
    "DISPLAY_3V3", "PANEL_3V3", "VBUS_USB", "BAT_RAW", "RX_RSSI_RAW",
    "VRX_VIDEO_RAW", "OSD_VIDEO_RAW", "AMT_RESET", "AMT_FLASH_CS",
    "AMT_FLASH_CLK", "AMT_FLASH_MOSI", "AMT_FLASH_MISO", "BUZZER_PWM",
    "BUZZER_LOW", "AUDIO_I2S_BCLK", "AUDIO_I2S_WS", "AUDIO_I2S_DATA",
    "AUDIO_ENABLE", "SPK+", "SPK-", "BL_LED_A", "BL_LED_K",
    "ESP_BOOT", "ESP_EN",
]
for index, net in enumerate(diagnostic_nets, 7):
    add(f"TP{index}", f"{net} test pad", "OpenPocket",
        "PCB-TEST-PAD-1.0MM", "N/A", "TEST-PAD-1.0MM", [("1", net)],
        42 + (index % 12) * 2.0, 43 + (index // 12) * 1.5, dnp=True,
        notes="bare ENIG copper test feature; not an assembled component")


def apply_placement() -> None:
    """Apply the reviewed two-sided functional floorplan.

    Converter loops and analog/video parts stay on L1.  Non-critical pull-ups,
    configuration resistors and factory pads are packed on L4, clear of the
    bottom-side RX5808 body and its solder/inspection area.
    """
    by_ref = {part.ref: part for part in P}
    assigned: set[str] = set()

    for part in P:
        if part.ref.startswith(("R", "C", "TP")):
            part.side = "B"

    def put(ref: str, x: float, y: float, side: str = "F",
            rotation: float = 0.0) -> None:
        part = by_ref[ref]
        part.x, part.y, part.side, part.rotation = x, y, side, rotation
        assigned.add(ref)

    def grid(refs: list[str], x: float, y: float, cols: int,
             dx: float, dy: float, side: str = "F") -> None:
        for index, ref in enumerate(refs):
            put(ref, x + (index % cols) * dx,
                y + (index // cols) * dy, side)

    # External interfaces and primary ICs.  The controls connector J9 spans
    # most of the lower edge, so its two GPIO expanders belong directly above
    # it.  Keeping them at the upper edge (as in the first seed) forced more
    # than thirty control nets to cross the entire board and made the design
    # needlessly hostile to both manual and automatic routing.
    fixed = {
        # The ESP is bottom-side and central, outside the RF/video keepout.
        "U1": (70, 31, "B"), "J2": (57.5, 5.4, "F"),
        # Battery entry is a tight chain from the lower-left pads into the
        # charger/protection parts; it no longer shares the display corridor.
        "U2": (57, 15, "F"), "U3": (12, 62, "F"),
        "Q1": (15, 56, "F"), "U4": (20, 55, "F"),
        "U20": (29, 58, "F"),
        # Split the two high-current converter islands.  U5 belongs with the
        # 3V3 logic/battery side; U6 and L3 belong with the 5V boost output.
        # Keeping them in one horizontal row made SYS_SWITCHED and the 5V
        # switch node compete with the display/control fan-out.
        "U5": (64, 43, "F"),
        "U6": (78, 46, "F"), "U7": (20, 40, "F"),
        "U8": (66, 57, "F"), "U9": (89, 63, "F"),
        # Rotate before the bottom-side flip so the ANT pad faces the optional
        # coax/U.FL launches at the left edge (final PCB orientation 0 deg).
        "U10": (60, 55, "F"), "MOD1": (22, 35, "B", 180),
        # Continuous video chain: RX5808 -> AT7456E -> AMT630A -> FFC.
        "U11": (29, 35, "F"), "U12": (20, 29, "F"),
        "U13": (34, 29, "F"), "U14": (44, 49, "F"),
        "U15": (54, 49, "F"), "U16": (60, 49, "F"),
        # Horizontal display FFC; keep the connector body ~10 mm above the
        # bottom edge so the cable can be inserted from below.
        "J1": (29.75, 62, "F"), "U17": (34, 58, "F"),
        "U18": (49, 61, "B"), "U19": (64, 61, "B"),
        "BZ1": (85, 7, "F"), "Q2": (79, 5, "B"),
        "D2": (79, 9, "B"), "U21": (78, 18, "B"),
        "J4": (100, 28, "F"), "U22": (87, 18, "B"),
        "J12": (101, 8.5, "F"), "ESD1": (52, 9, "F"),
        "ESD2": (94, 21, "F"),
        "ESD3": (99, 22, "F"),
        # Keep user-wired pad groups separated from the corner mounting holes.
        "J3": (12, 69.8, "F"), "J5": (25, 69.8, "F"),
        "J6": (101, 69.8, "F"),
        # Six-pad gimbal headers are spaced so the 2.8 mm pitch pads and
        # solder-mask apertures cannot overlap; the left header also clears
        # the 2 mm NPTH mounting hole at (4,4).
        "J7": (16.0, 3.5, "F"), "J8": (32.5, 3.5, "F"),
        # Bottom-side U.FL sits just outside the RX5808 body, allowing a short
        # via-free 5.8-GHz feed to the module ANT pad.
        # RF coax launch on the back, directly above the RX5808 module so
        # the 5.8 GHz feed remains short and avoids crossing the board.
        # U.FL is placed immediately to the right of the RX5808 shield.  A
        # 90-degree rotation puts its two ground fingers above/below the
        # launch, avoiding the module RF pad while keeping the coax feed
        # short and on the same bottom side.
        # Modular control groups are fixed to their enclosure-facing edges;
        # only the surrounding expanders/support logic may be optimized.
        "J9": (4.0, 14.0, "F"), "J18": (4.0, 50.0, "F"),
        "J19": (111.0, 22.0, "F", 180),
        "J20": (111.0, 28.0, "F", 180), "J21": (111.0, 32.0, "F", 180),
        "J22": (111.0, 46.0, "F", 180), "J23": (111.0, 52.0, "F", 180),
        "J24": (111.0, 60.0, "F", 180), "J25": (4.0, 57.0, "F"),
        "J26": (4.0, 64.0, "F"), "J11": (40.0, 42.6, "B", 90),
        "J13": (110, 40, "F"),
        # Developer pads are on the accessible right edge, clear of the
        # bottom-left RX5808/U.FL launch and the central analog-video island.
        "J14": (108, 18, "F"), "J15": (75, 68, "F"),
        "ESD4": (95, 65, "F"), "F1": (49, 14, "F"),
        "TVS1": (47.5, 18.5, "F"), "JP1": (37, 38, "F"),
        "Y1": (22, 35, "F"), "Y2": (33, 48, "F"),
        "L1": (64, 15, "F"), "L2": (59, 43, "F"),
        "L4": (51, 66, "F"),
        "L5": (74, 60, "F"), "D1": (44, 66, "F"),
        "FB1": (26, 43, "F"), "FB2": (33, 45, "F"),
        "FB3": (50, 40, "F"), "FB4": (54, 58, "F"),
    }
    for ref, position in fixed.items():
        put(ref, *position)
    # J1's cable opening faces the lower board edge; pin 1 is X=20.00 mm.
    put("J1", 29.75, 62, "F", 180)
    put("J2", 57.5, 5.4, "F", 90)
    # Put the 5-V boost switch-node pad on the U6-facing side of L3.
    put("L3", 88, 49, "F", 180)
    # ESP_EN is a local strap; do not leave its pull-up in the top generic
    # resistor bank 30 mm away from U1.
    put("R3", 24, 8, "B")

    # L1 critical support networks.
    grid(["R30", "R31", "R32", "R33", "R34", "R35"],
         43, 5, 2, 1.6, 1.6)
    grid(["R36", "R37", "R38", "R39", "C24", "C25", "C26", "C27"],
         26, 5, 4, 2.0, 2.0, "B")
    put("C27", 41, 17, "B")
    grid(["R42", "R43", "R44", "R45", "R46", "R47",
          "C28", "C29", "C30", "C31", "C32", "C33", "C34"],
         8.5, 42.5, 5, 2.5, 2.2)
    grid(["R56", "R57", "C67"], 2, 44, 3, 2.0, 2.0)
    grid(["R55", "C61", "C62"], 21, 44, 3, 2.0, 2.0)
    grid(["R4", "R48", "C2", "C3", "C23"], 27, 44, 3, 2.2, 2.2)
    grid(["R22", "R23", "R49", "C35", "C36", "C37", "C38", "C39"],
         34, 39, 4, 2.0, 2.0)
    grid(["R20", "R21", "R24", "R51", "R52", "C40", "C41", "C42",
          "C43", "C44", "C45", "C46", "C47", "C48", "C49", "C50"],
         44, 42.5, 6, 2.5, 2.4)
    grid(["R50", "C51", "C52", "C64", "C65", "C66"],
         72, 43, 3, 2.0, 2.0)
    grid(["R25", "R26", "R27", "C22", "C4", "C5", "C7",
          "C57", "C58", "C59", "C60"], 20, 58, 3, 2.0, 2.0)
    put("C6", 36, 40, "B")
    grid(["R10", "R11", "R12", "R53", "C8"], 40, 27, 1, 2.0, 1.7)
    grid(["R18", "C15", "C16"], 34, 18, 3, 1.8, 1.7)
    put("R58", 57, 40, "F")
    # AMT supply/boot parts fit beneath the centre of the LQFP body.  Keep
    # them away from the perimeter lead rows so their ground/signal vias do
    # not collide with opposite-side pads.
    grid(["R13", "C9", "C10", "C11", "C12", "C68", "C69", "C70",
          "C71", "C72", "C73"], 42, 27, 4, 2.0, 2.0, "B")
    grid(["R9", "C53", "C54", "C55", "C56"], 78, 38.5, 3, 2.2, 1.8)
    grid(["R6", "R7", "C17"], 80, 4, 3, 1.7, 1.7)
    grid(["R8", "R16", "C20", "C21"], 75, 21, 4, 2.0, 1.8, "B")
    grid(["R14", "R15"], 64, 16, 2, 2.0, 1.8)
    grid(["R59", "R60", "R61"], 45, 20, 3, 1.8, 1.8)
    grid(["R64", "R65", "R66", "R67", "R68", "R69"],
         28, 25, 3, 1.8, 1.6, "B")
    # Cell-protection gate resistors must sit with U3/Q1.  In the initial
    # catch-all bottom grid they ended up at the opposite board edge.
    grid(["R62", "R63"], 9, 50, 1, 1.8, 2.0, "B")
    put("R103", 46, 30, "F")
    put("R104", 18, 18, "F")
    grid(["R95", "R96", "R97", "R98", "C78", "C79", "C80", "C81"],
         20, 11, 4, 1.8, 1.8, "B")
    put("C79", 3, 16, "B")
    grid(["R99", "R100"], 20, 19, 2, 1.8, 1.8, "B")
    grid(["R101", "C82", "R102", "C83"], 80, 3, 2, 1.8, 1.8, "B")
    grid(["C74", "C75", "C76"], 70, 47, 3, 3.0, 2.5, "B")
    put("TP44", 60, 20, "B")
    put("TP45", 62, 20, "B")
    put("TP46", 64, 20, "B")

    # Put one local 100 nF/bulk capacitor directly below each flagged IC.
    # Short through-via stubs are preferable to the centimetre-scale loops in
    # the initial floorplan and keep the top-side escape channels available.
    put("C70", 70, 13, "B")   # U15 AMT boot flash
    put("C71", 77, 13, "B")   # U16 AMT flash mux
    put("C1", 68, 11, "B")    # U18 GPIO expander
    put("C53", 83, 27, "B")   # U17 backlight boost input
    put("C67", 3, 49, "B")    # U3 cell protector sense supply
    put("C4", 59, 52, "B")    # U7 video load-switch output

    # Critical support placement audit: these parts are deliberately
    # re-assigned after the legacy packing grids so moving an IC cannot leave
    # its decoupler, crystal loop or switch node stranded at the old seed.
    # AMT630A local island (U14 at 44,49).
    put("Y2", 33, 48, "F")
    put("R18", 39.5, 49, "B")
    put("C15", 39.5, 47, "B")
    put("C16", 39.5, 51, "B")
    for ref, pos in {
        "C9": (40, 53), "C10": (42, 54), "C11": (46, 54),
        "C12": (48, 53), "C68": (40, 55), "C69": (42, 56),
        "C70": (53, 53), "C71": (56, 53), "C72": (59, 53),
        "C73": (61, 55), "U15": (56, 35), "U16": (61, 37),
        "R5": (57, 47), "R13": (50, 47),
    }.items():
        if ref in by_ref:
            put(ref, *pos, "B" if ref.startswith(("R", "C")) else "F")

    # AT7456E local island and short crystal loop.
    put("Y1", 22, 35, "F")
    for ref, pos in {"C4": (26, 39), "C5": (28, 40), "C6": (34, 40),
                     "C57": (25, 32), "C58": (27, 32), "C59": (30, 32),
                     "C60": (32, 32), "R10": (32, 38), "R11": (34, 38),
                     "R12": (32, 34), "R53": (35, 33), "R58": (35, 37),
                     "R59": (20, 36), "R60": (21, 34), "R61": (22, 32)}.items():
        if ref in by_ref:
            put(ref, *pos, "B")

    # USB/charger entry island; all high-current support remains within a
    # few millimetres of U2 and the USB-C edge connector.
    for ref, pos in {"C28": (49, 11), "C29": (52, 14), "C30": (51, 16),
                     "C31": (53, 22), "C32": (57, 22), "C33": (61, 20),
                     "C34": (53, 10), "R40": (53, 18), "R41": (55, 18),
                     "R42": (52, 18), "R43": (54, 20), "R44": (56, 20),
                     "R45": (58, 20), "R46": (60, 20), "R47": (62, 20)}.items():
        if ref in by_ref:
            put(ref, *pos, "B")

    # Compact 3V3 and 5V converter islands.
    for ref, pos in {"C35": (62, 47), "C36": (62, 50), "C37": (66, 50),
                     "C38": (68, 47), "C39": (71, 47), "R22": (68, 42),
                     "R23": (71, 42), "R48": (70, 44), "R49": (73, 44),
                     "C40": (75, 42), "C41": (80, 42), "C42": (75, 50),
                     "C43": (82, 43), "C44": (82, 45), "C45": (72, 52),
                     "C46": (76, 53), "C47": (82, 52), "C48": (85, 52),
                     "C49": (88, 52), "C50": (91, 52), "R20": (84, 44),
                     "R21": (87, 44), "R24": (84, 47), "R51": (85, 49),
                     "R52": (87, 49)}.items():
        if ref in by_ref:
            put(ref, *pos, "B")

    # Backlight loop is adjacent to J1's LED pins; the boosted rail does not
    # cross the analog/RF area.
    for ref, pos in {"C51": (50, 57), "C53": (41, 54), "C54": (43, 61),
                     "C55": (46, 62), "C56": (49, 62), "C64": (53, 57),
                     "C65": (56, 57), "R9": (42, 61)}.items():
        if ref in by_ref:
            put(ref, *pos, "B")

    # SD and ELRS entry protection is at the connector, not at the source IC.
    for ref, pos in {"R30": (96, 5), "R31": (98, 5), "R32": (100, 5),
                     "R33": (96, 12), "R34": (98, 12), "R35": (100, 12),
                     "R36": (88, 13), "R37": (82, 10), "R38": (84, 10),
                     "R39": (86, 10), "C24": (88, 15), "C25": (90, 15),
                     "C26": (93, 15), "C27": (85, 15), "C74": (91, 64),
                     "C75": (94, 64), "C66": (92, 66)}.items():
        if ref in by_ref:
            put(ref, *pos, "B")

    # Gimbal ADC filters stay beside the ESP ADC side; control pull-ups remain
    # behind the two expanders near J9.
    for ref, pos in {"R95": (66, 35), "R96": (68, 35), "R97": (70, 35),
                     "R98": (72, 35), "C78": (66, 37), "C79": (68, 37),
                     "C80": (70, 37), "C81": (72, 37), "C1": (73, 28)}.items():
        if ref in by_ref:
            put(ref, *pos, "B")

    # Control pull-ups/filters are placed on L4 immediately below their
    # expanders.  This creates short via escapes to J9 and removes the dense
    # top-to-bottom ratsnest that defeated the first routing attempt.
    grid(["R70", "R73", "R74", "R75", "R76", "R77", "R78", "R79",
          "R80", "R81", "R82", "R83", "R84", "R85", "R86", "R87",
          "R88"], 31, 47, 6, 2.0, 1.6, "B")
    grid(["R89", "R90", "R91", "R92", "R93", "R94"],
         50, 47, 3, 2.0, 1.6, "B")

    # Remaining configuration parts and factory pads live on L4.  Their pack
    # starts to the right of the RX5808 shield/inspection rectangle.
    remaining = [part.ref for part in P
                 if (part.ref.startswith(("R", "C", "TP")) and
                     part.ref not in assigned)]
    grid(remaining, 31, 2, 24, 2.35, 2.15, "B")

    # The deterministic optimizer is an optional, versioned refinement of
    # this seed floorplan.  It is consumed here (rather than patching a PCB
    # after generation) so the generator remains authoritative and every
    # board/CPL/BOM regeneration uses the same placement manifest.
    if PLACEMENT_MANIFEST.is_file():
        data = json.loads(PLACEMENT_MANIFEST.read_text(encoding="utf-8"))
        placements = data.get("placements", {})
        if not isinstance(placements, dict):
            raise RuntimeError("placement-optimized.json: placements must be an object")
        for ref, item in placements.items():
            if ref not in by_ref:
                # Fiducials/mounting features are added directly during board
                # generation and are not members of the schematic Part list.
                # The optimizer may still record them as locked mechanical
                # context; leave those generator-owned features untouched.
                continue
            if not all(key in item for key in ("x_mm", "y_mm", "side", "rotation")):
                raise RuntimeError(f"placement manifest entry incomplete: {ref}")
            put(ref, float(item["x_mm"]), float(item["y_mm"]),
                str(item["side"]), float(item["rotation"]))
        # Modular control groups are mechanical user interfaces, not
        # optimizer candidates. Reassert their edge positions even when an
        # older manifest still contains the former J9/J16/J17 strips.
        for ref, x, y, side, rotation in (
                ("U1",65,31,"B",0),
                # Keep the expanders in the control region, but pull their
                # ESP-facing edges upward so U1 fanout does not cross the
                # entire FFC corridor.
                ("U18",53,55,"B",0),("U19",66,55,"B",0),
                # Keep the AMT flash mux outside the ESP32 backside body;
                # U15/U16 remain a compact flash island left of the ESP.
                ("U16",48,27,"F",0),
                ("J9",4,14,"F",0),("J18",4,50,"F",0),
                ("J19",111,22,"F",180),("J20",111,28,"F",180),
                ("J21",111,32,"F",180),("J22",111,46,"F",180),
                ("J23",111,52,"F",180),("J24",111,60,"F",180),
                ("J25",4,57,"F",0),("J26",4,64,"F",0),
                ("J15",75,68,"F",0),
                ("J14",108,18,"F",0),
                ("J13",110,40,"F",0),
                # Keep the charger PMID/BAT support caps beside U2 but not
                # under its exposed GND paddle or rear solder mask opening.
                ("C28",52,11,"B",0),("C31",52,19,"B",0),
                ("C32",58,21,"B",0)):
            put(ref, x, y, side, rotation)
        put("TVS1", 47.5, 18.5, "F", 0)
        # Keep the TFT FFC escape corridor clear.  J1 is a bottom-insertion
        # 0.5-mm-pitch connector; components directly behind its first 34
        # signal pads prevent a legal fanout and make the autorouter fail at
        # the connector.  These parts are support circuitry, so move them
        # outside the x=20..40 mm escape window while preserving their local
        # functional regions.
        for ref, x, y, side, rotation in (
                ("U4", 12, 53, "F", 0),
                ("U20", 62, 62, "F", 0),
                ("U17", 53, 60, "F", 0),
                ("R25", 16, 52, "F", 0),
                ("R26", 18, 52, "F", 0),
                ("R27", 20, 52, "F", 0),
                ("C22", 13, 55, "B", 0),
                ("D1", 58, 56, "F", 0),
                ("U10", 72, 54, "F", 0),
                ("U8", 68, 62, "F", 0),
                ("L4", 58, 66, "F", 0),
                # Back-side boost support is also kept out of the via escape
                # window; it remains immediately adjacent to the relocated
                # U17/D1 island.
                ("R86", 48, 53, "B", 0),
                ("R87", 50, 53, "B", 0),
                ("R88", 52, 53, "B", 0),
                ("C55", 48, 55, "B", 0),
                ("C56", 50, 55, "B", 0),
                ("C54", 52, 55, "B", 0),
                # Keep a clear fanout lane above the AMT630A's 0.4-mm
                # perimeter pads.  These small support parts stay on the
                # same logical video/clock island but no longer box in the
                # through-via escape candidates used by the router.
                ("R53", 36, 35, "B", 0),
                ("R58", 36, 37, "B", 0),
                ("R12", 35, 39, "B", 0),
                ("R11", 39, 34, "B", 0),
                ("C60", 40, 32, "B", 0),
                ("R77", 38, 43, "B", 0),
                ("C11", 50, 46, "B", 0),
                ("FB3", 52, 35, "F", 0),
                # Clear both sides of the AMT flash-mux escape.  C70/C71
                # remain local decouplers but no longer sit under the
                # fine-pitch C-MISO/C-MOSI/C-CLK perimeter pads.
                ("C70", 51, 33, "B", 0),
                ("C71", 53, 30, "B", 0),
                # ESP32-S3-MINI-1U fanout moat.  These passives/testpoints
                # were previously inside the bottom-side module projection,
                # blocking every perimeter escape even though the generic
                # courtyard check did not flag them.  Keep C1 local but
                # outside the module body; move non-critical filters and
                # testpoints beyond the 4-mm routing corridor.
                ("C1", 76, 30, "B", 0),
                ("C32", 54, 21, "B", 0),
                ("R45", 55, 18, "B", 0),
                ("R46", 58.5, 18.5, "B", 0),
                ("R47", 60.5, 18.5, "B", 0),
                ("C78", 74, 44, "B", 0),
                ("C79", 77, 44, "B", 0),
                ("C80", 80, 44, "B", 0),
                ("C81", 83, 44, "B", 0),
                ("TP44", 80, 26, "F", 0),
                ("TP45", 83, 26, "F", 0),
                ("TP46", 86, 26, "F", 0)):
            if ref in by_ref:
                put(ref, x, y, side, rotation)


apply_placement()

def ensure_nets(board):
    nets = sorted({net for part in P for _,_,net in pin_items(part)
                   if net not in ("NC","")})
    result = {}
    for name in nets:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        result[name] = net
    return result

def smd_pad(fp, number, x, y, sx, sy, net, layer):
    pad=pcbnew.PAD(fp); pad.SetNumber(str(number)); pad.SetShape(pcbnew.PAD_SHAPE_RECT)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD); pad.SetSize(pcbnew.VECTOR2I_MM(sx,sy))
    pad.SetPosition(pcbnew.VECTOR2I_MM(x,y));
    layers=pcbnew.LSET()
    for layer_id in (layer, pcbnew.B_Paste if layer==pcbnew.B_Cu else pcbnew.F_Paste,
                     pcbnew.B_Mask if layer==pcbnew.B_Cu else pcbnew.F_Mask):
        layers.AddLayer(layer_id)
    pad.SetLayerSet(layers)
    if net: pad.SetNet(net)
    fp.Add(pad)

def make_fp(board, part, nets):
    fp_id = footprint_id(part)
    if (fp_id.startswith("openpocket-easyeda:") or
            (fp_id.startswith("OpenPocket:") and
             (CUSTOM_FOOTPRINTS /
              f"{fp_id.split(':', 1)[1]}.kicad_mod").exists())):
        name = fp_id.split(":", 1)[1]
        library_path = (EASYEDA_FOOTPRINTS if
                        fp_id.startswith("openpocket-easyeda:") else
                        CUSTOM_FOOTPRINTS)
        fp = pcbnew.FootprintLoad(str(library_path), name, True)
        if fp is None:
            raise RuntimeError(f"{part.ref}: cannot load audited footprint {fp_id}")
        fp.SetReference(part.ref)
        fp.SetValue(part.value)
        fp.Reference().SetVisible(True)
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I_MM(0.65, 0.65))
        fp.Value().SetVisible(False)
        fp.SetPosition(pcbnew.VECTOR2I_MM(part.x, part.y))
        fp.SetOrientationDegrees(part.rotation)
        connections = {number: net for number, _, net in pin_items(part)}
        found: set[str] = set()
        for pad in fp.Pads():
            number = str(pad.GetNumber())
            if part.ref == "U6" and not number:
                pad.SetNet(nets[G])
                continue
            if (part.ref == "J2" and not number and
                    pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH):
                pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
                pad.SetNetCode(0)
                continue
            if number in connections:
                net_name = connections[number]
                if net_name not in ("NC", ""):
                    pad.SetNet(nets[net_name])
                found.add(number)
        # Some vendor land patterns intentionally use one pad number for two
        # fused package leads (for example TPS63070 VOUT 7/8 and VIN 12/13).
        # Accept the omitted logical number only when its net is already
        # represented by another physical pad; never silently drop a net.
        represented_nets = {connections[number] for number in found}
        missing = {number for number in set(connections) - found
                   if connections[number] not in represented_nets}
        if missing:
            raise RuntimeError(
                f"{part.ref}: footprint {fp_id} lacks schematic pads "
                f"{sorted(missing)}")
        board.Add(fp)
        # EasyEDA silkscreen clearances are not trusted.  Assembly detail is
        # retained on Fab; reviewed board-level reference/pin-1 marks are
        # emitted separately below.
        for item in fp.GraphicalItems():
            if item.GetLayer() == pcbnew.F_SilkS:
                item.SetLayer(pcbnew.F_Fab)
            elif item.GetLayer() == pcbnew.B_SilkS:
                item.SetLayer(pcbnew.B_Fab)
        if part.side == "B":
            fp.Flip(fp.GetPosition(), False)
        fp.SetDNP(part.dnp)
        fp.SetExcludedFromBOM(part.dnp)
        return fp
    fp=pcbnew.FOOTPRINT(board); fp.SetReference(part.ref); fp.SetValue(part.value)
    fp.Reference().SetVisible(True); fp.Value().SetVisible(False)
    # Create on the front; Flip() below moves bottom-side fields to B.Fab.
    fp.Reference().SetLayer(pcbnew.F_Fab)
    fp.Reference().SetTextSize(pcbnew.VECTOR2I_MM(0.65, 0.65))
    lib_id=pcbnew.LIB_ID()
    lib_id.SetLibNickname(pcbnew.UTF8("OpenPocket"))
    lib_id.SetLibItemName(pcbnew.UTF8(re.sub(r"[^A-Za-z0-9_.+-]","_",part.package)))
    fp.SetFPID(lib_id)
    fp.SetPosition(pcbnew.VECTOR2I_MM(part.x,part.y)); fp.SetAttributes(pcbnew.FP_SMD)
    fp.SetOrientationDegrees(part.rotation)
    if part.side=="B": fp.Flip(fp.GetPosition(), False)
    layer=pcbnew.B_Cu if part.side=="B" else pcbnew.F_Cu
    count=len(part.pins)
    if part.ref=="J1":
        for i,(number,_,netname) in enumerate(pin_items(part)):
            smd_pad(fp,number,part.x+1.8,part.y+(i-19.5)*0.5,2.4,0.3,nets.get(netname),layer)
    elif part.ref=="MOD1":
        for i,(number,_,netname) in enumerate(pin_items(part)):
            side=-1 if i<6 else 1; idx=i if i<6 else 11-i
            smd_pad(fp,number,part.x+side*11.9,part.y+(idx-2.5)*2.54,2.4,1.4,nets.get(netname),layer)
    elif part.ref=="J12":
        # TF-001A-P3 land pattern derived from the SOFNG vertical-view drawing.
        # Signal pads P1..P8 are 0.80-mm pitch. P9 is the normally-open CD
        # contact; pads 10..13 are the four mechanical shell anchors.
        signal_x=[-1.925,-1.125,-0.325,0.475,1.275,2.075,2.875,3.675]
        for i,xoff in enumerate(signal_x):
            smd_pad(fp,i+1,part.x+xoff,part.y-4.05,0.40,1.50,
                    nets.get(part.pins[i][1]),layer)
        smd_pad(fp,9,part.x+3.085,part.y+6.40,0.85,1.30,
                nets.get(part.pins[8][1]),layer)
        anchors=[(-6.005,-4.05),(6.275,-4.05),(-1.925,6.40),(4.385,6.40)]
        for i,(xoff,yoff) in enumerate(anchors,10):
            smd_pad(fp,i,part.x+xoff,part.y+yoff,1.40,1.90,nets.get(G),layer)
    elif part.ref=="U1":
        for i,(number,_,netname) in enumerate(pin_items(part)):
            if i<15: x=part.x-7.3; y=part.y-7+(i)*1
            elif i<30: x=part.x-7+(i-15)*1; y=part.y+8.0
            elif i<45: x=part.x+7.3; y=part.y+7-(i-30)*1
            else:
                j=i-45; x=part.x-5.5+(j%5)*2.75; y=part.y-4+(j//5)*2.5
            smd_pad(fp,number,x,y,0.9,0.55,nets.get(netname),layer)
    elif part.ref=="J2":
        for i,(number,_,netname) in enumerate(pin_items(part)):
            smd_pad(fp,number,part.x+(i-7.5)*0.5,part.y+2,0.3,1.3,nets.get(netname),layer)
    elif count<=4:
        for i,(number,_,netname) in enumerate(pin_items(part)):
            smd_pad(fp,number,part.x+(i-(count-1)/2)*0.9,part.y,0.65,0.8,nets.get(netname),layer)
    else:
        left=(count+1)//2; pitch=0.4 if count>=48 else (0.5 if count>=14 else 0.65)
        span=(left-1)*pitch
        width=7.6 if count>=48 else (5.2 if count>=14 else 3.2)
        for i,(number,_,netname) in enumerate(pin_items(part)):
            if i<left: x=part.x-width/2; y=part.y-span/2+i*pitch
            else: x=part.x+width/2; y=part.y+span/2-(i-left)*pitch
            smd_pad(fp,number,x,y,0.75 if count<14 else 1.0,pitch*0.55,nets.get(netname),layer)
    # Assembly body. Courtyards are emitted by the verified package library;
    # this generated board copy intentionally does not invent a generic one.
    body_width,body_height=(14.55,15.80) if part.ref=="J12" else (5,5)
    for layer_id,width,height in [(pcbnew.F_Fab,body_width,body_height)]:
        if part.side=="B": layer_id=pcbnew.B_Fab
        rect=pcbnew.PCB_SHAPE(fp); rect.SetShape(pcbnew.SHAPE_T_RECT)
        rect.SetStart(pcbnew.VECTOR2I_MM(part.x-width/2,part.y-height/2)); rect.SetEnd(pcbnew.VECTOR2I_MM(part.x+width/2,part.y+height/2)); rect.SetLayer(layer_id); rect.SetWidth(pcbnew.FromMM(0.05)); fp.Add(rect)
    fp.SetDNP(part.dnp)
    fp.SetExcludedFromBOM(part.dnp)
    board.Add(fp); return fp


def add_developer_pad_labels(board: pcbnew.BOARD) -> None:
    """Add readable F.Silk labels for all user-accessible pad groups."""
    labels = {
        "J3": ("BATTERY", ["BAT+", "BAT-", "NTC", "GND"]),
        "J5": ("MASTER SW", ["SW-A", "SW-B"]),
        "J6": ("ELRS 4-WIRE", ["5V", "GND", "RX", "TX"]),
        "J7": ("GIMBAL L", ["LX", "3V3", "GND", "LY", "3V3", "GND"]),
        "J8": ("GIMBAL R", ["RX", "3V3", "GND", "RY", "3V3", "GND"]),
        "J11": ("5.8G U.FL", ["RF", "GND", "GND"]),
        "J13": ("SPEAKER", ["SPK+", "SPK-"]),
        "J14": ("OLED 128x64", ["GND", "3V3", "SDA", "SCL"]),
        "J15": ("DEV IO", ["IO0", "IO1", "IO2", "IO3", "3V3", "GND"]),
    }
    for ref, (heading, names) in labels.items():
        fp = next((item for item in board.GetFootprints()
                   if item.GetReference() == ref), None)
        if fp is None:
            raise RuntimeError(f"{ref}: developer pad footprint missing")
        center_y = fp.GetPosition().y
        for pad, name in zip(fp.Pads(), names):
            pos = pad.GetPosition()
            text = pcbnew.PCB_TEXT(board)
            text.SetText(name)
            # Keep labels inside the board outline, at least 0.8 mm clear of
            # the exposed pad. Rotate edge labels so long names do not merge.
            if ref in {"J3", "J6"}:
                # These bottom-edge power headers sit beside the left/right
                # control groups and fiducials.  A compact, inboard legend
                # avoids both while staying paired with the solder pads.
                text.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y - pcbnew.FromMM(3.0)))
                text.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
                text.SetTextSize(pcbnew.VECTOR2I_MM(0.55, 0.55))
            elif pcbnew.ToMM(pos.y) > BOARD_HEIGHT - 5:
                text.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y - pcbnew.FromMM(6.0)))
                text.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
            elif pcbnew.ToMM(pos.y) < 5:
                text.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y + pcbnew.FromMM(4.0)))
                text.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
            elif pcbnew.ToMM(pos.x) < 8:
                text.SetPosition(pcbnew.VECTOR2I(pos.x + pcbnew.FromMM(4.0), pos.y))
            elif ref == "J14":
                # The OLED header shares the right-edge service region with
                # ESD and speaker copper.  Its pad legends need a larger
                # inward offset than ordinary edge pads.
                text.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y + pcbnew.FromMM(6.0)))
            else:
                delta = -4.0 if pos.y < center_y else 4.0
                text.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y + pcbnew.FromMM(delta)))
            # All user-facing pads are on the top copper side, so their
            # identifiers belong on the same top silkscreen side.
            text.SetLayer(pcbnew.F_SilkS)
            text.SetMirrored(False)
            text.SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
            text.SetTextThickness(pcbnew.FromMM(0.08))
            text.SetHorizJustify(0)  # KiCad SWIG enum: centered
            board.Add(text)
        # The individual U.FL RF/GND and developer-pad legends already state
        # the interface unambiguously.  A second title cannot clear adjacent
        # copper in these deliberately dense service regions.
        if ref in {"J11", "J15"}:
            continue
        title = pcbnew.PCB_TEXT(board)
        title.SetText(heading)
        # The rotated U.FL has its RF/ground lands on a vertical axis. Keep
        # the title outside the launch body so the three pad labels remain
        # legible and do not overlap one another.
        if ref == "J11":
            title.SetPosition(pcbnew.VECTOR2I_MM(
                pcbnew.ToMM(fp.GetPosition().x) + 7.0,
                pcbnew.ToMM(fp.GetPosition().y) + 7.0))
            title.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
            title.SetLayer(pcbnew.B_SilkS)
            title.SetMirrored(True)
        elif ref == "J5":
            title.SetPosition(pcbnew.VECTOR2I_MM(25.0, 56.0))
        elif ref == "J6":
            title.SetPosition(pcbnew.VECTOR2I_MM(101.0, 56.0))
        elif ref == "J15":
            title.SetPosition(pcbnew.VECTOR2I_MM(75.0, 54.0))
        elif ref == "J17":
            title.SetPosition(pcbnew.VECTOR2I_MM(
                pcbnew.ToMM(fp.GetPosition().x) - 6.0,
                pcbnew.ToMM(fp.GetPosition().y)))
        elif pcbnew.ToMM(fp.GetPosition().x) < 8:
            title.SetPosition(pcbnew.VECTOR2I(fp.GetPosition().x + pcbnew.FromMM(8.0),
                                              fp.GetPosition().y))
        else:
            title_y = (fp.GetPosition().y + pcbnew.FromMM(7.0)
                       if pcbnew.ToMM(center_y) < 5 else
                       fp.GetPosition().y - pcbnew.FromMM(10.0))
            title.SetPosition(pcbnew.VECTOR2I(fp.GetPosition().x, title_y))
        if ref != "J11":
            title.SetLayer(pcbnew.F_SilkS)
            title.SetMirrored(False)
        title.SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
        title.SetTextThickness(pcbnew.FromMM(0.10))
        title.SetHorizJustify(0)  # KiCad SWIG enum: centered
        board.Add(title)
    brand = pcbnew.PCB_TEXT(board)
    brand.SetText("OpenPocket")
    brand.SetPosition(pcbnew.VECTOR2I_MM(75.0, 2.0))
    brand.SetLayer(pcbnew.F_SilkS)
    brand.SetTextSize(pcbnew.VECTOR2I_MM(1.4, 1.4))
    brand.SetTextThickness(pcbnew.FromMM(0.20))
    brand.SetHorizJustify(0)
    board.Add(brand)
    # Control-function labels now live inside each modular group footprint;
    # avoid a detached numbered legend that can be mistaken for a separate
    # connector or ground bank.


def legalize_small_parts(board: pcbnew.BOARD) -> None:
    """Nudge passives/test pads out of courtyard and pad collisions.

    The functional floorplan supplies each part's preferred location.  This
    pass only performs local mechanical legalization; it does not alter the
    location of ICs, connectors, crystals, inductors, RF/video modules or the
    analog path ordering.
    """
    movable = {part.ref for part in P
               if part.ref.startswith(("R", "C", "TP"))}
    part_by_ref = {part.ref: part for part in P}
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    margin = pcbnew.FromMM(0.20)

    def has_pth(fp: pcbnew.FOOTPRINT) -> bool:
        return any(pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,
                                          pcbnew.PAD_ATTRIB_NPTH)
                   for pad in fp.Pads())

    def side_keys(fp: pcbnew.FOOTPRINT) -> tuple[str, ...]:
        if has_pth(fp):
            return ("F", "B")
        return ("B",) if fp.GetLayer() == pcbnew.B_Cu else ("F",)

    def box(fp: pcbnew.FOOTPRINT, side: str) -> pcbnew.BOX2I:
        layer = pcbnew.B_CrtYd if side == "B" else pcbnew.F_CrtYd
        courtyard = fp.GetCourtyard(layer)
        pads = None
        for pad in fp.Pads():
            pad_box = pad.GetBoundingBox()
            if pads is None:
                pads = pcbnew.BOX2I(pad_box.GetOrigin(), pad_box.GetSize())
            else:
                pads.Merge(pad_box)
        if pads is None:
            pads = fp.GetBoundingBox()
        result = pads
        if not courtyard.IsEmpty():
            result.Merge(courtyard.BBox())
        return result.GetInflated(margin)

    occupied: dict[str, list[pcbnew.BOX2I]] = {"F": [], "B": []}
    for ref, fp in footprints.items():
        if ref in movable:
            continue
        for side in side_keys(fp):
            occupied[side].append(box(fp, side))

    # Reserve the inspected RF module and U.FL launch as real placement
    # keepouts.  Their pad bounding boxes are intentionally smaller than the
    # shield/cable clearance, so treating only pads as occupied let passives
    # drift into the RF courtyard and made the placement optimizer reject its
    # own best state.
    for ref in ("MOD1", "J11"):
        fp = footprints.get(ref)
        if fp is None:
            continue
        for side in side_keys(fp):
            rf_box = box(fp, side)
            rf_box.Inflate(pcbnew.FromMM(2.0))
            occupied[side].append(rf_box)

    # Large capacitors are placed before 0402 parts, then test pads fill the
    # remaining gaps.  This makes the result deterministic across KiCad runs.
    ordered = sorted((footprints[ref] for ref in movable),
                     key=lambda fp: (-fp.GetBoundingBox().GetArea(),
                                     fp.GetReference()))
    for fp in ordered:
        desired = fp.GetPosition()
        sides = side_keys(fp)
        chosen = None
        # 0.5-mm local spiral, then a board-wide 1-mm fallback.  The latter is
        # only expected for the dense bottom-side factory-pad bank.
        candidates = [(0.0, 0.0)]
        for radius in [0.5 * i for i in range(1, 25)]:
            steps = int(radius / 0.5)
            for index in range(-steps, steps + 1):
                candidates.extend(((index * 0.5, -radius),
                                   (index * 0.5, radius),
                                   (-radius, index * 0.5),
                                   (radius, index * 0.5)))
        for dx, dy in candidates:
            candidate = pcbnew.VECTOR2I(desired.x + pcbnew.FromMM(dx),
                                        desired.y + pcbnew.FromMM(dy))
            fp.SetPosition(candidate)
            boxes = [box(fp, side) for side in sides]
            if any(bb.GetLeft() < pcbnew.FromMM(1.0) or
                   bb.GetRight() > pcbnew.FromMM(BOARD_WIDTH - 1.0) or
                   bb.GetTop() < pcbnew.FromMM(1.0) or
                   bb.GetBottom() > pcbnew.FromMM(BOARD_HEIGHT - 1.0) for bb in boxes):
                continue
            if any(bb.Intersects(other) for side, bb in zip(sides, boxes)
                   for other in occupied[side]):
                continue
            chosen = (candidate, boxes)
            break
        if chosen is None:
            raise RuntimeError(f"{fp.GetReference()}: no legal local placement")
        fp.SetPosition(chosen[0])
        for side, bb in zip(sides, chosen[1]):
            occupied[side].append(bb)
        part = part_by_ref[fp.GetReference()]
        part.x = chosen[0].x / 1_000_000
        part.y = chosen[0].y / 1_000_000


def configure_project_netclasses(project: pathlib.Path) -> None:
    """Write deterministic KiCad netclasses and exact net assignments."""
    if not project.exists():
        raise RuntimeError(
            f"{project.name} is required before board generation so routing "
            "constraints cannot be silently omitted")
    data = json.loads(project.read_text(encoding="utf-8"))
    net_settings = data.setdefault("net_settings", {})
    available = {net for part in P for _, _, net in pin_items(part)
                 if net not in ("", "NC")}
    assigned: dict[str, str] = {}
    for class_name, members in NET_CLASS_MEMBERS.items():
        unknown = members - available
        if unknown:
            raise RuntimeError(
                f"{class_name}: unknown routing nets {sorted(unknown)}")
        for net in members:
            if net in assigned:
                raise RuntimeError(
                    f"{net}: assigned to both {assigned[net]} and "
                    f"{class_name}")
            assigned[net] = class_name

    classes = []
    for priority, (name, rules) in enumerate(NET_CLASS_RULES):
        classes.append({
            "bus_width": 12,
            "clearance": rules["clearance"],
            "diff_pair_gap": rules["diff_pair_gap"],
            "diff_pair_via_gap": rules["diff_pair_gap"],
            "diff_pair_width": rules["diff_pair_width"],
            "line_style": 0,
            "microvia_diameter": 0.30,
            "microvia_drill": 0.10,
            "name": name,
            "pcb_color": "rgba(0, 0, 0, 0.000)",
            "priority": (2147483647 if name == "Default" else priority),
            "schematic_color": "rgba(0, 0, 0, 0.000)",
            "track_width": rules["track_width"],
            "via_diameter": rules["via_diameter"],
            "via_drill": rules["via_drill"],
            "wire_width": 6,
        })
    net_settings["classes"] = classes
    net_settings["netclass_assignments"] = None
    net_settings["netclass_patterns"] = [
        {"netclass": class_name, "pattern": net}
        for net, class_name in sorted(assigned.items())
    ]
    net_settings.setdefault("meta", {})["version"] = 4
    project.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def add_fiducial(board: pcbnew.BOARD, reference: str, x: float, y: float,
                  side: str) -> None:
    """Add a 1 mm copper / 2 mm mask assembly fiducial."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(reference)
    fp.SetValue("Fiducial_1mm_Mask2mm")
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM |
                     pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    lib_id = pcbnew.LIB_ID()
    lib_id.SetLibNickname(pcbnew.UTF8("OpenPocket"))
    lib_id.SetLibItemName(pcbnew.UTF8("Fiducial_1mm_Mask2mm"))
    fp.SetFPID(lib_id)
    fp.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    layer = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu
    fp.SetLayer(layer)
    pad = pcbnew.PAD(fp)
    pad.SetNumber("")
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    pad.SetSize(pcbnew.VECTOR2I_MM(1.0, 1.0))
    pad.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    pad.SetLocalSolderMaskMargin(pcbnew.FromMM(0.5))
    layers = pcbnew.LSET()
    layers.AddLayer(layer)
    layers.AddLayer(pcbnew.B_Mask if side == "B" else pcbnew.F_Mask)
    pad.SetLayerSet(layers)
    fp.Add(pad)
    board.Add(fp)


def add_mounting_hole(board: pcbnew.BOARD, reference: str, x: float, y: float,
                      diameter: float = 2.0) -> None:
    """Add a plated-free 2 mm mechanical mounting hole."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(reference)
    fp.SetValue("MountingHole_2mm")
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM |
                     pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    pad = pcbnew.PAD(fp)
    pad.SetNumber("")
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetSize(pcbnew.VECTOR2I_MM(diameter, diameter))
    pad.SetDrillSize(pcbnew.VECTOR2I_MM(diameter, diameter))
    layers = pcbnew.LSET()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.F_Mask, pcbnew.B_Mask):
        layers.AddLayer(layer)
    pad.SetLayerSet(layers)
    pad.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    fp.Add(pad)
    mark = pcbnew.PCB_SHAPE(fp)
    mark.SetShape(pcbnew.SHAPE_T_CIRCLE)
    mark.SetCenter(pcbnew.VECTOR2I_MM(x, y))
    mark.SetEnd(pcbnew.VECTOR2I_MM(x + diameter / 2 + 0.5, y))
    mark.SetLayer(pcbnew.F_Fab)
    mark.SetWidth(pcbnew.FromMM(0.05))
    fp.Add(mark)
    board.Add(fp)


def add_exposed_pad_thermal_vias(board: pcbnew.BOARD, nets: dict) -> None:
    """Add tented, footprint-embedded thermal vias to exposed ground pads."""
    patterns = {
        "U2": ("25", (-0.8, 0.0, 0.8), (-0.8, 0.0, 0.8)),
        "U11": ("29", (-2.2, 0.0, 2.2), (-0.75, 0.0, 0.75)),
        "U21": ("9", (-0.8, 0.0, 0.8), (-0.6, 0.0, 0.6)),
    }
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for reference, (pad_number, x_offsets, y_offsets) in patterns.items():
        footprint = footprints[reference]
        center = footprint.GetPosition()
        for x_offset in x_offsets:
            for y_offset in y_offsets:
                via = pcbnew.PAD(footprint)
                via.SetNumber(pad_number)
                via.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
                via.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
                via.SetSize(pcbnew.VECTOR2I_MM(0.45, 0.45))
                via.SetDrillSize(pcbnew.VECTOR2I_MM(0.20, 0.20))
                via.SetLayerSet(pcbnew.LSET.AllCuMask())
                via.SetPosition(pcbnew.VECTOR2I(
                    center.x + pcbnew.FromMM(x_offset),
                    center.y + pcbnew.FromMM(y_offset)))
                via.SetNet(nets[G])
                footprint.Add(via)


def configure_plane_connections(board: pcbnew.BOARD) -> None:
    """Use solid L2 ground connections for high-current edge connectors."""
    for reference in ("J3", "J6"):
        footprint = board.FindFootprintByReference(reference)
        for pad in footprint.Pads():
            if (pad.GetNetname() == G and
                    pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH):
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


def add_ground_fanout(board: pcbnew.BOARD, nets: dict) -> None:
    """Give every outer-layer SMD ground pad a short, tented L2 escape.

    A continuous inner ground plane is only useful when the outer-layer pads
    can actually reach it.  Leaving this to the autorouter produced hundreds
    of long ground detours and even signal tracks on the intended plane.  The
    deterministic local fanout below keeps L2 free of signal routing and makes
    each ground connection explicit before bulk routing starts.
    """
    ground = nets[G]
    rule_by_class = {name: rules for name, rules in NET_CLASS_RULES}
    default_clearance = rule_by_class["Default"]["clearance"]
    net_clearance = {
        net: rule_by_class[class_name]["clearance"]
        for class_name, members in NET_CLASS_MEMBERS.items()
        for net in members
    }
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()]
    through = [pad for pad in pads
               if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,
                                         pcbnew.PAD_ATTRIB_NPTH)]
    occupied_vias: list[tuple[float, float]] = [
        (pad.GetPosition().x / 1_000_000, pad.GetPosition().y / 1_000_000)
        for pad in through
    ]
    ground_access: list[tuple[float, float]] = [
        (pad.GetPosition().x / 1_000_000, pad.GetPosition().y / 1_000_000)
        for pad in through if pad.GetNetname() == G
    ]

    def bbox_mm(pad: pcbnew.PAD) -> tuple[float, float, float, float]:
        box = pad.GetBoundingBox()
        return (box.GetLeft() / 1_000_000, box.GetTop() / 1_000_000,
                box.GetRight() / 1_000_000, box.GetBottom() / 1_000_000)

    def copper_layer(pad: pcbnew.PAD) -> int:
        return (pcbnew.B_Cu if
                pad.GetParentFootprint().GetLayer() == pcbnew.B_Cu else
                pcbnew.F_Cu)

    obstacles = [(pad, bbox_mm(pad)) for pad in pads]

    def point_clear(x: float, y: float, own: pcbnew.PAD) -> bool:
        if not (0.65 <= x <= BOARD_WIDTH - 0.65 and
                0.65 <= y <= BOARD_HEIGHT - 0.65):
            return False
        if any(math.hypot(x - vx, y - vy) < 0.65
               for vx, vy in occupied_vias):
            return False
        for other, (left, top, right, bottom) in obstacles:
            if other is own or other.GetNetname() == G:
                continue
            clearance = (0.225 + max(0.10, net_clearance.get(
                other.GetNetname(), default_clearance)) + 0.02)
            if (left - clearance <= x <= right + clearance and
                    top - clearance <= y <= bottom + clearance):
                return False
        return True

    def segment_clear(x1: float, y1: float, x2: float, y2: float,
                      own: pcbnew.PAD) -> bool:
        # Sampling is conservative enough for the sub-2-mm straight stubs and
        # avoids inventing a second geometry engine beside KiCad's DRC.
        length = math.hypot(x2 - x1, y2 - y1)
        samples = max(2, math.ceil(length / 0.10))
        for index in range(1, samples + 1):
            scale = index / samples
            x = x1 + (x2 - x1) * scale
            y = y1 + (y2 - y1) * scale
            for other, (left, top, right, bottom) in obstacles:
                if other is own or other.GetNetname() == G:
                    continue
                if not other.IsOnLayer(copper_layer(own)):
                    continue
                clearance = (0.10 + max(0.10, net_clearance.get(
                    other.GetNetname(), default_clearance)) + 0.02)
                if (left - clearance <= x <= right + clearance and
                        top - clearance <= y <= bottom + clearance):
                    return False
        return True

    def junction_clear(x0: float, y0: float, x: float, y: float,
                       layer: int) -> bool:
        """Reject acute shared-via branches that form copper slivers."""
        new_x, new_y = x0 - x, y0 - y
        new_length = math.hypot(new_x, new_y)
        for item in board.GetTracks():
            if isinstance(item, pcbnew.PCB_VIA) or item.GetLayer() != layer:
                continue
            start, end = item.GetStart(), item.GetEnd()
            sx, sy = start.x / 1_000_000, start.y / 1_000_000
            ex, ey = end.x / 1_000_000, end.y / 1_000_000
            if math.hypot(sx - x, sy - y) < 0.001:
                other_x, other_y = ex - x, ey - y
            elif math.hypot(ex - x, ey - y) < 0.001:
                other_x, other_y = sx - x, sy - y
            else:
                continue
            other_length = math.hypot(other_x, other_y)
            if not new_length or not other_length:
                continue
            cosine = max(-1.0, min(1.0,
                (new_x * other_x + new_y * other_y) /
                (new_length * other_length)))
            if math.degrees(math.acos(cosine)) < 30.0:
                return False
        return True

    smd_ground = [pad for pad in pads
                  if pad.GetNetname() == G and
                  pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    smd_ground.sort(key=lambda pad: (
        pad.GetParentFootprint().GetReference(), str(pad.GetNumber()),
        pad.GetPosition().x, pad.GetPosition().y))
    missing: list[str] = []
    for pad in smd_ground:
        # User-facing edge/header pads are intentionally left for the normal
        # router/ground zones.  A deterministic local via is not possible at
        # the board edge and would recreate the unwanted holes beside these
        # hand-solder pads.
        if pad.GetParentFootprint().GetReference() in {
                "J3", "J5", "J6", "J7", "J8", "J9", "J13", "J14",
                "J15", "J18", "J19", "J20", "J21", "J22", "J23",
                "J24", "J25", "J26"}:
            continue
        pad_box = pad.GetBoundingBox()
        if any(other.GetNetname() == G and
               other.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and
               pad_box.Intersects(other.GetBoundingBox())
               for other in through):
            continue
        position = pad.GetPosition()
        x0, y0 = position.x / 1_000_000, position.y / 1_000_000
        footprint = pad.GetParentFootprint()
        # Adjacent ground pins may share a nearby via or grounded through-pad;
        # this is especially useful for consecutive LQFP supply pins.
        reachable = [(x, y) for x, y in
                     sorted(ground_access,
                            key=lambda point: math.hypot(
                                point[0] - x0, point[1] - y0))
                     if math.hypot(x - x0, y - y0) <= 4.00 and
                     segment_clear(x0, y0, x, y, pad)]
        existing = next(((x, y) for x, y in reachable
                         if junction_clear(x0, y0, x, y,
                                           copper_layer(pad))), None)
        fallback_existing = reachable[0] if reachable else None
        if existing is not None:
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(position)
            track.SetEnd(pcbnew.VECTOR2I_MM(*existing))
            track.SetWidth(pcbnew.FromMM(0.20))
            track.SetLayer(copper_layer(pad))
            track.SetNet(ground)
            board.Add(track)
            continue
        center = footprint.GetPosition()
        dx, dy = x0 - center.x / 1_000_000, y0 - center.y / 1_000_000
        if abs(dx) >= abs(dy):
            outward = (1 if dx >= 0 else -1, 0)
        else:
            outward = (0, 1 if dy >= 0 else -1)
        directions = [outward, (1, 0), (-1, 0), (0, 1), (0, -1),
                      (1, 1), (-1, 1), (1, -1), (-1, -1)]
        candidate = None
        for distance in (0.75, 0.95, 1.20, 1.50, 1.85, 2.25, 2.80,
                         3.50):
            if candidate:
                break
            for ux, uy in directions:
                norm = math.hypot(ux, uy)
                x = x0 + distance * ux / norm
                y = y0 + distance * uy / norm
                if (point_clear(x, y, pad) and
                        segment_clear(x0, y0, x, y, pad)):
                    candidate = (x, y, None)
                    break
            if candidate:
                break
        # Fine-pitch perimeter pads often cannot accept a via on their centre
        # line because the via annulus would touch both neighbouring pads.
        # Escape radially first, then move tangentially outside the lead row.
        if candidate is None:
            ox, oy = outward
            tangents = ((-oy, ox), (oy, -ox))
            for radial in (0.80, 1.00, 1.25, 1.55):
                waypoint = (x0 + radial * ox, y0 + radial * oy)
                if not segment_clear(x0, y0, *waypoint, pad):
                    continue
                for tangent in (0.60, 0.85, 1.10, 1.40):
                    for tx, ty in tangents:
                        x = waypoint[0] + tangent * tx
                        y = waypoint[1] + tangent * ty
                        if (point_clear(x, y, pad) and
                                segment_clear(*waypoint, x, y, pad)):
                            candidate = (x, y, waypoint)
                            break
                    if candidate:
                        break
                if candidate:
                    break
        if candidate is None:
            # Fine-pitch pads can be boxed in by neighbouring lands.  Reuse
            # the nearest reachable ground access only when no independent
            # via is geometrically possible.
            if fallback_existing is not None:
                track = pcbnew.PCB_TRACK(board)
                track.SetStart(position)
                track.SetEnd(pcbnew.VECTOR2I_MM(*fallback_existing))
                track.SetWidth(pcbnew.FromMM(0.20))
                track.SetLayer(copper_layer(pad))
                track.SetNet(ground)
                board.Add(track)
                continue
            missing.append(
                f"{footprint.GetReference()}.{pad.GetNumber()}")
            continue
        x, y, waypoint = candidate
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        via.SetWidth(pcbnew.FromMM(0.45))
        via.SetDrill(pcbnew.FromMM(0.20))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(ground)
        via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        board.Add(via)
        occupied_vias.append((x, y))
        ground_access.append((x, y))
        points = [(x0, y0)]
        if waypoint is not None:
            points.append(waypoint)
        points.append((x, y))
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I_MM(*start))
            track.SetEnd(pcbnew.VECTOR2I_MM(*end))
            track.SetWidth(pcbnew.FromMM(0.20))
            track.SetLayer(copper_layer(pad))
            track.SetNet(ground)
            board.Add(track)
    if missing:
        # Dense QFN/BGA ground pins can be reached by the plane or autorouter
        # when no local via spot remains.  Do not block board generation over
        # these optional deterministic fanouts.
        print("ground fanout deferred for " + ", ".join(missing))


def add_reviewed_logic_fanout(board: pcbnew.BOARD, nets: dict) -> None:
    """Route the U5 3V3 output directly into its nearest bulk capacitor.

    This is a reviewed local supply branch, not an autorouter import.  The
    through-via sits outside U5's exposed-pad courtyard, and the short B.Cu
    branch terminates at C39's 22-uF output capacitor.
    """
    net = nets["3V3_LOGIC"]

    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I_MM(67.0, 42.0))
    via.SetWidth(pcbnew.FromMM(0.55))
    via.SetDrill(pcbnew.FromMM(0.25))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(via)
    for layer, start, end in (
            (pcbnew.F_Cu, (65.4, 42.54), (67.0, 42.0)),
            (pcbnew.B_Cu, (67.0, 42.0), (67.035, 46.035))):
        track = pcbnew.PCB_TRACK(board)
        track.SetLayer(layer)
        track.SetWidth(pcbnew.FromMM(0.40))
        track.SetStart(pcbnew.VECTOR2I_MM(*start))
        track.SetEnd(pcbnew.VECTOR2I_MM(*end))
        track.SetNet(net)
        board.Add(track)


def add_reviewed_battery_fanout(board: pcbnew.BOARD, nets: dict) -> None:
    """Route the short, high-current battery-entry branches deterministically.

    J3 is an edge SMD wire pad, while the protection parts are several layers
    of dense control/decoupling placement away.  Leaving these first branches
    to the generic router causes it to spend the opening pass trying to cross
    the edge-control pads.  The reviewed SIG1 corridor stays clear of those
    pads and the mounting-hole keepout; the remaining long charger branches
    are intentionally left for the constrained router/manual review.
    """
    def add_track(net_name: str, layer: int,
                  start: tuple[float, float], end: tuple[float, float],
                  width: float = 0.40) -> None:
        net = nets.get(net_name)
        if net is None:
            return
        item = pcbnew.PCB_TRACK(board)
        item.SetLayer(layer)
        item.SetWidth(pcbnew.FromMM(width))
        item.SetStart(pcbnew.VECTOR2I_MM(*start))
        item.SetEnd(pcbnew.VECTOR2I_MM(*end))
        item.SetNet(net)
        board.Add(item)

    def add_via(net_name: str, position: tuple[float, float]) -> None:
        net = nets.get(net_name)
        if net is None:
            return
        item = pcbnew.PCB_VIA(board)
        item.SetPosition(pcbnew.VECTOR2I_MM(*position))
        item.SetWidth(pcbnew.FromMM(0.45))
        item.SetDrill(pcbnew.FromMM(0.20))
        item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        item.SetNet(net)
        item.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        item.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        board.Add(item)

    # BAT_RAW: J3.1 -> R56.1, on SIG1 through the left-side corridor.  The
    # dogleg at y=66.3 stays outside MH3 and the edge-control pads.
    add_via("BAT_RAW", (7.8, 68.4))
    add_via("BAT_RAW", (2.0, 43.2))
    add_track("BAT_RAW", pcbnew.F_Cu, (7.8, 69.8), (7.8, 68.4), 0.30)
    add_track("BAT_RAW", pcbnew.In2_Cu, (7.8, 68.4), (7.8, 66.3))
    add_track("BAT_RAW", pcbnew.In2_Cu, (7.8, 66.3), (2.0, 66.3))
    add_track("BAT_RAW", pcbnew.In2_Cu, (2.0, 66.3), (2.0, 43.2))
    add_track("BAT_RAW", pcbnew.F_Cu, (2.0, 43.2), (1.57, 44.0), 0.30)

    # BAT_CELL_NEG: J3.2 -> U3.4 -> Q1.1.  The through-via stubs keep the
    # SMD pads on the accessible top side while SIG1 remains obstacle-free.
    add_via("BAT_CELL_NEG", (10.6, 68.4))
    add_via("BAT_CELL_NEG", (12.64, 63.4))
    add_via("BAT_CELL_NEG", (16.35, 57.8))
    add_track("BAT_CELL_NEG", pcbnew.F_Cu, (10.6, 69.8), (10.6, 68.4), 0.30)
    add_track("BAT_CELL_NEG", pcbnew.In2_Cu, (10.6, 68.4), (10.6, 64.5))
    add_track("BAT_CELL_NEG", pcbnew.In2_Cu, (10.6, 64.5), (12.64, 63.4))
    add_track("BAT_CELL_NEG", pcbnew.F_Cu, (12.64, 63.4), (12.64, 62.5), 0.30)
    add_track("BAT_CELL_NEG", pcbnew.In2_Cu, (12.64, 63.4), (16.35, 57.8))
    add_track("BAT_CELL_NEG", pcbnew.F_Cu, (16.35, 57.8), (16.35, 56.95), 0.30)

def generate_board():
    # pcbnew assigns UUIDs while objects and library footprints are added.
    # A fixed generator seed makes repeated source generation byte-stable;
    # the electrical/mechanical identity is already defined by this script.
    pcbnew.KIID.SeedGenerator(0x4F504B54)
    b=pcbnew.BOARD(); b.GetDesignSettings().SetCopperLayerCount(8)
    b.SetLayerName(pcbnew.F_Cu, "F.Cu")
    b.SetLayerName(pcbnew.In1_Cu, "GND1")
    b.SetLayerName(pcbnew.In2_Cu, "SIG1")
    b.SetLayerName(pcbnew.In3_Cu, "SIG2")
    b.SetLayerName(pcbnew.In4_Cu, "SIG3")
    b.SetLayerName(pcbnew.In5_Cu, "SIG4")
    b.SetLayerName(pcbnew.In6_Cu, "GND2")
    b.SetLayerName(pcbnew.B_Cu, "B.Cu")
    ds=b.GetDesignSettings(); ds.m_MinClearance=pcbnew.FromMM(0.10); ds.m_TrackMinWidth=pcbnew.FromMM(0.12); ds.m_ViasMinSize=pcbnew.FromMM(0.45); ds.m_MinThroughDrill=pcbnew.FromMM(0.20); ds.m_SolderMaskMinWidth=pcbnew.FromMM(0.0)
    nets=ensure_nets(b)
    for part in P: make_fp(b,part,nets)
    add_developer_pad_labels(b)
    legalize_small_parts(b)
    configure_plane_connections(b)
    for reference, x, y, side in [
            ("FID1", 16, 20, "F"), ("FID2", 90, 22, "F"),
            ("FID3", 100, 64, "F"), ("FID4", 16, 8, "B"),
            ("FID5", 98, 9, "B"), ("FID6", 98, 64, "B")]:
        add_fiducial(b, reference, x, y, side)
    for reference, x, y in [("MH1", 4, 4), ("MH2", 111, 4),
                            ("MH3", 4, 68), ("MH4", 111, 68)]:
        add_mounting_hole(b, reference, x, y, 2.0)
    add_exposed_pad_thermal_vias(b, nets)
    add_ground_fanout(b, nets)
    add_reviewed_logic_fanout(b, nets)
    add_reviewed_battery_fanout(b, nets)
    for a,c in [((0, 0), (BOARD_WIDTH, 0)),
                ((BOARD_WIDTH, 0), (BOARD_WIDTH, BOARD_HEIGHT)),
                ((BOARD_WIDTH, BOARD_HEIGHT), (0, BOARD_HEIGHT)),
                ((0, BOARD_HEIGHT), (0, 0))]:
        s=pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(pcbnew.VECTOR2I_MM(*a)); s.SetEnd(pcbnew.VECTOR2I_MM(*c)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(.1)); b.Add(s)
    # Continuous L2/L7 ground-reference planes. Signal routing is forbidden
    # on both by the critical-routing audit.
    for plane in (pcbnew.In1_Cu, pcbnew.In6_Cu):
        z=pcbnew.ZONE(b); z.SetLayer(plane); z.SetNet(nets[G]); z.SetLocalClearance(pcbnew.FromMM(.2)); z.SetMinThickness(pcbnew.FromMM(.15));
        out=z.Outline(); out.NewOutline()
        for x,y in [(0.25, 0.25), (BOARD_WIDTH - 0.25, 0.25),
                    (BOARD_WIDTH - 0.25, BOARD_HEIGHT - 0.25),
                    (0.25, BOARD_HEIGHT - 0.25)]:
            out.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        b.Add(z)
    # microSD 11 x 15 mm card body: locked and 3.12-mm farther out at eject.
    for name,start,end in [
        ("MICROSD CARD LOCKED",(26.5,0.2),(37.5,15.2)),
        ("MICROSD CARD EJECTED",(26.5,-2.92),(37.5,12.08)),
        ("MICROSD FINGER ACCESS",(24.5,-4.0),(39.5,4.0))]:
        rect=pcbnew.PCB_SHAPE(b); rect.SetShape(pcbnew.SHAPE_T_RECT)
        rect.SetStart(pcbnew.VECTOR2I_MM(*start)); rect.SetEnd(pcbnew.VECTOR2I_MM(*end))
        rect.SetLayer(pcbnew.User_2); rect.SetWidth(pcbnew.FromMM(0.15)); b.Add(rect)
        # Keep the mechanical outlines unlabeled on the production board.
    pcbnew.SaveBoard(str(BOARD),b)
    # The 0.4-mm AMT630A pitch is designed to JLC's 0.10-mm copper rule.
    board_text=BOARD.read_text()
    board_text=board_text.replace("(thickness 1.6)", "(thickness 1.0)", 1)
    board_text=board_text.replace("(clearance 0.2)",
                                  "(clearance 0.1)", 1)
    BOARD.write_text(board_text)
    apply_stackup_metadata()
    sync_footprint_metadata()
    project=ROOT/"openpocket-rev-a.kicad_pro"
    configure_project_netclasses(project)
    # The reviewed Specctra session is versioned so the routed result can be
    # recreated from this exact placement. pcbnew rejects sessions whose
    # component or net identifiers no longer match the generated design.
    if ROUTING.exists():
        routed=pcbnew.LoadBoard(str(BOARD))
        if not pcbnew.ImportSpecctraSES(routed, str(ROUTING)):
            raise RuntimeError(f"cannot import routing session {ROUTING}")
        pcbnew.SaveBoard(str(BOARD), routed)
    # ZONE_FILLER is unstable on a board freshly created through KiCad 9's
    # SWIG API, but reliable after reloading the saved file in a clean process.
    # Keep that isolation explicit so generated boards always store valid
    # L2/L7 copper and DRC/Specctra never treat GND as an ordinary unrouted
    # signal.
    subprocess.run([sys.executable, str(__file__), "--stage", "fill"],
                   check=True)


def apply_stackup_metadata() -> None:
    board_text = BOARD.read_text()
    if "\n\t\t(stackup\n" in board_text:
        return
    stackup = '''\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.100) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 2" (type "core") (thickness 0.100) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.100) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
\t\t\t(layer "In3.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 4" (type "core") (thickness 0.100) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
\t\t\t(layer "In4.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 5" (type "prepreg") (thickness 0.100) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
\t\t\t(layer "In5.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 6" (type "core") (thickness 0.100) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
\t\t\t(layer "In6.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 7" (type "prepreg") (thickness 0.100) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)\n'''
    marker = "\t(setup\n"
    if marker not in board_text:
        raise RuntimeError("cannot locate KiCad setup block for stack-up")
    BOARD.write_text(board_text.replace(marker, marker + stackup, 1))


def sync_footprint_metadata() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for part in P:
        footprint = footprints.get(part.ref)
        if footprint is None:
            raise RuntimeError(f"{part.ref}: missing from generated PCB")
        fp_id = footprint_id(part)
        nickname, item = fp_id.split(":", 1)
        library_path = (EASYEDA_FOOTPRINTS if
                        nickname == "openpocket-easyeda" else
                        CUSTOM_FOOTPRINTS)
        if ((nickname == "openpocket-easyeda") or
                (nickname == "OpenPocket" and
                 (library_path / f"{item}.kicad_mod").exists())):
            # These footprints are deliberately modified after load, so keep
            # them detached from library-comparison DRC while retaining the
            # reviewed item name.
            nickname = ""
        lib_id = pcbnew.LIB_ID()
        lib_id.SetLibNickname(pcbnew.UTF8(nickname))
        lib_id.SetLibItemName(pcbnew.UTF8(item))
        footprint.SetFPID(lib_id)
        footprint.SetDNP(part.dnp)
        footprint.SetExcludedFromBOM(part.dnp)
        if footprint.HasFieldByName("LCSC Part"):
            footprint.GetFieldByName("LCSC Part").SetText(part.lcsc)
    pcbnew.SaveBoard(str(BOARD), board)


def fill_board() -> None:
    project = ROOT / "openpocket-rev-a.kicad_pro"
    project_bytes = project.read_bytes()
    board = pcbnew.LoadBoard(str(BOARD))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    # Loading/saving a board can make pcbnew reorder netclasses in the
    # project file.  Filling copper must not create a noisy semantic no-op.
    project.write_bytes(project_bytes)

def symbol_library():
    lines=['(kicad_symbol_lib (version 20231120) (generator openpocket)']
    for part in P:
        name=re.sub(r"[^A-Za-z0-9_.+-]","_",part.ref+"_"+part.mpn)
        left=(len(part.pins)+1)//2
        right=len(part.pins)-left
        # Keep every pin endpoint on KiCad's 50-mil connection grid.  Using a
        # centred half-step for even pin counts produces visually neat boxes,
        # but ERC quite correctly reports every endpoint as off grid.
        half=max(5,(max(left,right)//2+1)*1.27)
        lines += [f'  (symbol "{name}" (pin_names (offset 1.0)) (exclude_from_sim no) (in_bom yes) (on_board yes)',
          f'    (property "Reference" "{re.sub(r"[0-9_].*", "", part.ref)}" (at 0 {half+2} 0) (effects (font (size 1.27 1.27))))',
          f'    (property "Value" "{part.mpn}" (at 0 {-half-2} 0) (effects (font (size 1.0 1.0))))',
          f'    (property "Footprint" "{footprint_id(part)}" (at 0 0 0) (effects (font (size 1.0 1.0)) hide))',
          '    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.0 1.0)) hide))',
          f'    (symbol "{name}_0_1" (rectangle (start -7.62 {half}) (end 7.62 {-half}) (stroke (width 0) (type default)) (fill (type background))))',
          f'    (symbol "{name}_1_1"']
        for i,(number,pin,_) in enumerate(pin_items(part)):
            if i<left: x=-10.16; y=(left//2-i)*1.27; rot=0
            else: x=10.16; y=((i-left)-right//2)*1.27; rot=180
            pname=pin.replace('"','')
            lines.append(f'      (pin bidirectional line (at {x} {y:.3f} {rot}) (length 2.54) (name "{pname}" (effects (font (size 0.8 0.8)))) (number "{number}" (effects (font (size 0.8 0.8)))))')
        lines += ['    )','  )']
    lines.append(')'); LIBRARY.write_text('\n'.join(lines)+'\n')

def schematic_groups():
    groups={}
    for i,part in enumerate(P):
        # Use the reviewed, per-device symbol emitted by ``symbol_library``.
        # The earlier seed used generic connector symbols.  Apart from being
        # misleading to a reviewer, the 64-pin connector substitute reordered
        # the AMT630A pins and made labels from adjacent devices overlap.
        lib_id=LIBRARY.stem+":"+re.sub(r"[^A-Za-z0-9_.+-]","_",part.ref+"_"+part.mpn)
        groups.setdefault(lib_id,[]).append((i,part))
    return list(groups.items())


def set_sourcing_properties(component, part: Part) -> None:
    """Keep production sourcing data in the KiCad schematic source of truth."""
    component.add_properties({
        "MPN": part.mpn,
        "Manufacturer": part.manufacturer,
        "LCSC": part.lcsc,
        "DNP": "yes" if part.dnp else "no",
        "BOM Comments": part.notes,
    }, hidden=True)
    component.in_bom = not part.dnp
    component.on_board = True

def schematic_init():
    import os
    import kicad_sch_api as ksa
    generate_custom_footprints()
    (ROOT/'sym-lib-table').write_text(
        '(sym_lib_table (version 7)\n'
        '  (lib (name "openpocket-rev-a")(type "KiCad")(uri "${KIPRJMOD}/openpocket-rev-a.kicad_sym")(options "")(descr "Reviewed Rev-A symbols"))\n'
        '  (lib (name "openpocket-easyeda")(type "KiCad")(uri "${KIPRJMOD}/easyeda/openpocket-easyeda.kicad_sym")(options "")(descr "Audited JLC source symbols"))\n'
        ')\n')
    (ROOT/'fp-lib-table').write_text(
        '(fp_lib_table (version 7)\n'
        '  (lib (name "OpenPocket")(type "KiCad")(uri "${KIPRJMOD}/openpocket-rev-a.pretty")(options "")(descr "Reviewed custom Rev-A footprints"))\n'
        '  (lib (name "openpocket-easyeda")(type "KiCad")(uri "${KIPRJMOD}/easyeda/openpocket-easyeda.pretty")(options "")(descr "Audited JLC source footprints"))\n'
        ')\n')
    # create_schematic() may reopen an existing file instead of replacing it;
    # explicitly start from an empty generated source for deterministic staged
    # regeneration.
    SCHEMATIC.unlink(missing_ok=True)
    previous=os.getcwd(); os.chdir(ROOT)
    sch=ksa.create_schematic("OpenPocket Rev A Engineering Prototype")
    sch.add_text("OpenPocket Rev A — Engineering Prototype",(20,8),size=2.0)
    sch.save(SCHEMATIC)
    os.chdir(previous)

def schematic_group(group_index, group_count=1):
    import os
    import kicad_sch_api as ksa
    previous=os.getcwd(); os.chdir(ROOT)
    sch=ksa.load_schematic(SCHEMATIC)
    sch.library.add_library_path(LIBRARY)
    selected=schematic_groups()[group_index:group_index+group_count]
    with sch.components.batch_mode():
        for lib_id,items in selected:
            for i,part in items:
                x=25+(i%6)*38; y=20+(i//6)*35
                sch.components.add(lib_id,part.ref,part.value,position=(x,y),
                                   footprint=footprint_id(part))
    for _,items in selected:
        for _,part in items:
            set_sourcing_properties(sch.components.get(part.ref), part)
            for pin_number,_,net in pin_items(part):
                if net not in ("NC",""):
                    sch.add_label(net,pin=(part.ref,pin_number))
                else:
                    sch.add_label(f"NC_{part.ref}_{pin_number}",
                                  pin=(part.ref,pin_number))
    sch.save(SCHEMATIC)
    os.chdir(previous)

def schematic():
    import os
    import kicad_sch_api as ksa
    schematic_init()
    previous=os.getcwd(); os.chdir(ROOT)
    sch=ksa.load_schematic(SCHEMATIC)
    sch.library.add_library_path(LIBRARY)
    with sch.components.batch_mode():
        for i,part in enumerate(P):
            x=25+(i%6)*38; y=20+(i//6)*35
            lib_id=LIBRARY.stem+":"+re.sub(
                r"[^A-Za-z0-9_.+-]","_",part.ref+"_"+part.mpn)
            sch.components.add(lib_id,part.ref,part.value,position=(x,y),
                               footprint=footprint_id(part))
    for part in P:
        component=sch.components.get(part.ref)
        set_sourcing_properties(component, part)
        component_x=float(component.position.x)
        for pin_number,_,net in pin_items(part):
            pos=sch.get_component_pin_position(part.ref,pin_number)
            if net in ("NC",""):
                sch.no_connects.add(pos)
                continue
            direction=-1 if float(pos.x)<component_x else 1
            end=(pos.x+direction*2.54,pos.y)
            sch.add_wire(pos,end)
            sch.add_label(net,position=end,
                          rotation=0 if direction<0 else 180)
    sch.save(SCHEMATIC)
    os.chdir(previous)

def schematic_connect_init():
    import kicad_sch_api as ksa
    sch=ksa.load_schematic(SCHEMATIC)
    sch.labels.clear(); sch.wires.clear(); sch.no_connects.clear()
    sch.save(SCHEMATIC)

def schematic_connect_group(group_index, group_count=1):
    import kicad_sch_api as ksa
    sch=ksa.load_schematic(SCHEMATIC)
    sch.library.add_library_path(LIBRARY)
    selected=schematic_groups()[group_index:group_index+group_count]
    for _,items in selected:
        for _,part in items:
            component=sch.components.get(part.ref)
            component_x=float(component.position.x)
            for pin_number,_,net in pin_items(part):
                pos=sch.get_component_pin_position(part.ref,pin_number)
                if net in ("NC",""):
                    sch.no_connects.add(pos)
                    continue
                # Every generated symbol has pins on its left and right edges.
                # Extend the wire away from the body before placing the label.
                direction=-1 if float(pos.x)<component_x else 1
                end=(pos.x+direction*2.54,pos.y)
                sch.add_wire(pos,end)
                sch.add_label(net,position=end,rotation=0 if direction<0 else 180)
    sch.save(SCHEMATIC)

def tables():
    # Pick-and-place coordinates come from the actual legalized board rather
    # than the preferred floorplan. This keeps independently regenerated CPL
    # files aligned with the PCB.
    if not BOARD.exists():
        raise RuntimeError("generated PCB is required before generating tables")
    board=pcbnew.LoadBoard(str(BOARD))
    board_parts={fp.GetReference(): fp for fp in board.GetFootprints()}
    for part in P:
        fp=board_parts.get(part.ref)
        if fp is None:
            raise RuntimeError(f"{part.ref}: missing from generated PCB")
        position=fp.GetPosition()
        part.x=position.x / 1_000_000
        part.y=position.y / 1_000_000
        part.side="B" if fp.GetLayer() == pcbnew.B_Cu else "F"
        part.rotation=fp.GetOrientationDegrees()
    fields=["Designator","Value","Manufacturer","MPN","LCSC","Package","Qty","DNP","Notes"]
    for filename in ["bom.csv","bom-jlcpcb.csv","bom-generic.csv"]:
        with (ROOT/filename).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
            for p in P: w.writerow(dict(zip(fields,[p.ref,p.value,p.manufacturer,p.mpn,p.lcsc,p.package,1,"yes" if p.dnp else "no",p.notes])))
    with (ROOT/"design-netlist.json").open('w') as f:
        json.dump({p.ref:{"mpn":p.mpn,"package":p.package,
            "pins":{number:net for number,_,net in pin_items(p)}} for p in P},
            f,indent=2,sort_keys=True)
    with (ROOT/"cpl-generic.csv").open('w',newline='') as f:
        w=csv.writer(f,lineterminator="\n"); w.writerow(["Designator","Mid X","Mid Y","Layer","Rotation"])
        for p in P:
            if not p.dnp: w.writerow([p.ref,f"{p.x:.3f}",f"{p.y:.3f}","Bottom" if p.side=="B" else "Top",f"{p.rotation:.1f}"])
    with (ROOT/"cpl-jlcpcb.csv").open('w',newline='') as f:
        w=csv.writer(f,lineterminator="\n"); w.writerow(["Designator","Mid X","Mid Y","Layer","Rotation"])
        for p in P:
            if not p.dnp: w.writerow([p.ref,f"{p.x:.3f}mm",f"{p.y:.3f}mm","Bottom" if p.side=="B" else "Top",f"{p.rotation:.1f}"])
    amt=next(part for part in P if part.ref=="U14")
    amt_functions={1:"CVBS1",2:"CVBS2",3:"CVBS3",4:"VCOM_ADC",5:"AVSS_ADC",
      6:"P0.3/REMOTE",7:"SAR2",8:"SAR1",9:"SAR0",10:"DVDD",11:"VDD_CORE_OUT",
      12:"GND",13:"AGND",14:"XTAL_OUT",15:"XTAL_IN",16:"AVDD",17:"SPI_CS",
      18:"SPI_SI",19:"SPI_SO",20:"SPI_CLK",21:"DVDD",22:"VDD_CORE_OUT",
      23:"GND",40:"DVDD",41:"VDD_CORE_OUT",42:"GND",51:"DCLK",52:"DE",
      53:"HSYNC",54:"VSYNC",55:"PWM0",56:"PWM1",57:"UART0",58:"UART1",
      59:"DIAGNOSTIC",60:"SDA",61:"SCL",62:"DVDD",63:"RESET",64:"AVDD_ADC"}
    for pin in range(24,32): amt_functions[pin]=f"R{pin-24}"
    for pin in range(32,40): amt_functions[pin]=f"G{pin-32}"
    for pin in range(43,51): amt_functions[pin]=f"B{pin-43}"
    with (ROOT/"amt630a-pin-audit.csv").open('w',newline='') as f:
        fields=["pin","primary_function","selected_function","final_net",
                "electrical_type","supply_domain","default_pull",
                "test_point","source_evidence"]
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        for pin,(_,net) in enumerate(amt.pins,1):
            function=amt_functions[pin]
            domain=("analog-3v3" if pin in (1,2,3,4,5,13,16,64)
                    else "core-1v2-output" if pin in (11,22,41)
                    else "digital-3v3")
            w.writerow(dict(pin=pin,primary_function=function,
                selected_function=function,final_net=net,
                electrical_type="power" if pin in (5,10,11,12,13,16,21,22,23,40,41,42,62,64) else "bidirectional",
                supply_domain=domain,
                default_pull="100k high" if pin==63 else "none",
                test_point="yes" if net.startswith("TP_") else "no",
                source_evidence="AMT630A_Spec_V1.2.pdf pp.6-9; C9900018923 CAD; public AMT630A pin reference; KiCad U14"))
    rx=next(part for part in P if part.ref=="MOD1")
    with (ROOT/"rx5808-pin-audit.csv").open('w',newline='') as f:
        fields=["pin","function","net","pad_x_mm","pad_y_mm","evidence"]
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        rx_footprint=board_parts[rx.ref]
        rx_pads={pad.GetNumber(): pad for pad in rx_footprint.Pads()}
        for index,(function,net) in enumerate(rx.pins):
            pad=rx_pads[str(index+1)]; position=pad.GetPosition()
            w.writerow(dict(pin=index+1,function=function,net=net,
                pad_x_mm=f"{pcbnew.ToMM(position.x):.3f}",
                pad_y_mm=f"{pcbnew.ToMM(position.y):.3f}",
                evidence="C2908157 EasyEDA footprint; 28x23 mm module geometry; published 12-pad order"))
    sd=next(part for part in P if part.ref=="J12")
    with (ROOT/"microsd-pin-audit.csv").open('w',newline='') as f:
        fields=["pin","function","net","pad_x_mm","pad_y_mm",
                "card_present_logic","source_evidence"]
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        sd_footprint=board_parts[sd.ref]
        sd_pads={pad.GetNumber(): pad for pad in sd_footprint.Pads()}
        for index,(function,net) in enumerate(sd.pins[:8]):
            position=sd_pads[str(index+1)].GetPosition()
            w.writerow(dict(pin=index+1,function=function,net=net,
                pad_x_mm=f"{pcbnew.ToMM(position.x):.3f}",
                pad_y_mm=f"{pcbnew.ToMM(position.y):.3f}",card_present_logic="n/a",
                source_evidence="SOFNG TF-001A-P3 drawing, vertical-view land pattern, P1-P8 at 0.80 mm pitch"))
        position=sd_pads["9"].GetPosition()
        w.writerow(dict(pin=9,function="CARD_DETECT",net="SD_CARD_DETECT",
            pad_x_mm=f"{pcbnew.ToMM(position.x):.3f}",
            pad_y_mm=f"{pcbnew.ToMM(position.y):.3f}",
            card_present_logic="low=fully inserted",
            source_evidence="SOFNG TF-001A-P3 normally-open CD-to-ground switch drawing"))

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",choices=("all","lib","sch-init","sch-group","sch-connect-init","sch-connect-group","board","fill","stackup","metadata","netclasses","tables"),default="all")
    parser.add_argument("--group",type=int)
    parser.add_argument("--group-count",type=int,default=1)
    args=parser.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    if args.stage in ("all","lib"):
        generate_custom_footprints()
        symbol_library()
    if args.stage=="all": schematic()
    elif args.stage=="sch-init": schematic_init()
    elif args.stage=="sch-group": schematic_group(args.group,args.group_count)
    elif args.stage=="sch-connect-init": schematic_connect_init()
    elif args.stage=="sch-connect-group": schematic_connect_group(args.group,args.group_count)
    if args.stage in ("all","board"): generate_board()
    elif args.stage=="fill": fill_board()
    elif args.stage=="stackup": apply_stackup_metadata()
    elif args.stage=="metadata": sync_footprint_metadata()
    elif args.stage=="netclasses": configure_project_netclasses(
        ROOT/"openpocket-rev-a.kicad_pro")
    if args.stage in ("all","tables"): tables()
    print(f"generated stage={args.stage} parts={len(P)} groups={len(schematic_groups())}")
