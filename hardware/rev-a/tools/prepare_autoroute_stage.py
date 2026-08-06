#!/usr/bin/env python3
"""Build a staged Freerouting DSN by selecting net classes and rule widths."""
from __future__ import annotations

import argparse
from pathlib import Path
import re


def balanced_end(text: str, start: int) -> int:
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError("unterminated S-expression")


def tokens(source: str) -> list[str]:
    return [item.strip('"') for item in re.findall(r'"[^"]+"|\S+', source)]


def class_members(text: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    start = text.index("  (network")
    stop = text.index("  (wiring", start)
    for match in re.finditer(r'\n    \(class ("[^"]+"|[^\s()]+)\s+', text[start:stop]):
        block_start = start + match.start() + 1
        block_end = balanced_end(text, block_start)
        block = text[block_start:block_end]
        name = match.group(1).strip('"')
        prefix = block[:block.index("(circuit")]
        payload = prefix.split(None, 2)[2]
        result[name] = set(tokens(payload))
    return result


def replace_pin_lists(text: str, keep_nets: set[str]) -> tuple[str, int]:
    network_start = text.index("  (network")
    class_start = text.index("    (class ", network_start)
    net_section = text[network_start:class_start]
    replacements: list[tuple[int, int, str]] = []
    for match in re.finditer(r'\n    \(net ("[^"]+"|[^\s()]+)', net_section):
        block_start = network_start + match.start() + 1
        block_end = balanced_end(text, block_start)
        name = match.group(1).strip('"')
        if name in keep_nets:
            continue
        block = text[block_start:block_end]
        pins = re.search(r'\(pins(?:\s.*?)?\)', block, re.S)
        if pins is None:
            continue
        updated = block[:pins.start()] + "(pins)" + block[pins.end():]
        replacements.append((block_start, block_end, updated))
    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]
    return text, len(replacements)


def override_class(text: str, spec: str) -> str:
    # CLASS=width_um,clearance_um,Via[0-7]_diameter:drill_um
    name, values = spec.split("=", 1)
    width, clearance, via = values.split(",", 2)
    marker = f"    (class {name} "
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"missing class {name}")
    end = balanced_end(text, start)
    block = text[start:end]
    block = re.sub(r'\(use_via "Via\[0-7\]_[0-9]+:[0-9]+_um"\)',
                   f'(use_via "{via}")', block)
    block = re.sub(r'\(width [0-9]+\)', f'(width {int(width)})', block)
    block = re.sub(r'\(clearance [0-9]+\)',
                   f'(clearance {int(clearance)})', block)
    return text[:start] + block + text[end:]


def remove_planes(text: str, net_names: set[str]) -> tuple[str, int]:
    removed = 0
    for name in net_names:
        pattern = re.compile(r'\n\s*\(plane\s+' + re.escape(name) + r'\s+')
        while True:
            match = pattern.search(text)
            if match is None:
                break
            start = match.start() + 1
            end = balanced_end(text, start)
            text = text[:start] + text[end:]
            removed += 1
    return text, removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-classes", default="")
    parser.add_argument("--exclude-classes", default="")
    parser.add_argument("--empty-nets", default="")
    parser.add_argument("--remove-plane-nets", default="")
    parser.add_argument("--class-rule", action="append", default=[])
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    members = class_members(text)
    include = {item for item in args.include_classes.split(",") if item}
    exclude = {item for item in args.exclude_classes.split(",") if item}
    if include and exclude:
        raise SystemExit("use either include or exclude classes")

    all_nets = set().union(*members.values()) if members else set()
    if include:
        missing = include - set(members)
        if missing:
            raise SystemExit(f"unknown classes: {sorted(missing)}")
        keep = set().union(*(members[name] for name in include))
    else:
        keep = set(all_nets)
        for name in exclude:
            if name not in members:
                raise SystemExit(f"unknown class {name}")
            keep -= members[name]
    keep -= {item for item in args.empty_nets.split(",") if item}

    text, emptied = replace_pin_lists(text, keep)
    for spec in args.class_rule:
        text = override_class(text, spec)
    text, removed = remove_planes(
        text, {item for item in args.remove_plane_nets.split(",") if item}
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(f"KEPT_NETS={len(keep)}")
    print(f"EMPTIED_NET_BLOCKS={emptied}")
    print(f"REMOVED_PLANES={removed}")
    print(f"STAGE_DSN={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
