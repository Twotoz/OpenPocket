#!/usr/bin/env python3
"""Remove GND ratsnest pins from a Freerouting DSN.

The board has dedicated, protected GND planes.  Routing every GND pad as an
ordinary signal trace wastes most autorouter time and can never legally use the
reserved plane layers.  This helper keeps the GND net, class, and plane shapes
in the DSN but empties only the GND pin list.  GND fanout/stitching is added to
the KiCad board after signal routing.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def find_balanced_block(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError("unterminated S-expression block")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    marker = "    (net GND\n"
    occurrences = text.count(marker)
    if occurrences != 1:
        raise SystemExit(f"expected one GND net block, found {occurrences}")
    start = text.index(marker)
    end = find_balanced_block(text, start)
    original = text[start:end]
    if "(pins " not in original and "(pins\n" not in original:
        raise SystemExit("GND net does not contain a pin list")
    pin_count = original.count("-")

    replacement = "    (net GND\n      (pins)\n    )"
    output = text[:start] + replacement + text[end:]

    for required in (
        "    (class Ground GND\n",
        "    (plane GND (polygon GND1",
        "    (plane GND (polygon GND2",
        "      (type power)",
    ):
        if required not in output:
            raise SystemExit(f"required protected-GND construct missing: {required!r}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(f"GND_PIN_TOKENS_REMOVED={pin_count}")
    print(f"SIGNAL_ONLY_DSN={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
