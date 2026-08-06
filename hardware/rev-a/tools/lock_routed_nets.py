#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pcbnew


def item_netname(item) -> str:
    try:
        return item.GetNetname()
    except AttributeError:
        net = item.GetNet()
        return net.GetNetname() if net else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--nets", required=True)
    args = parser.parse_args()

    selected = {name for name in args.nets.split(",") if name}
    board = pcbnew.LoadBoard(str(args.input))
    locked = 0
    for item in board.GetTracks():
        if item_netname(item) in selected:
            item.SetLocked(True)
            locked += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output), board)
    print(f"LOCKED_ITEMS={locked}")
    print(f"LOCKED_BOARD={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
