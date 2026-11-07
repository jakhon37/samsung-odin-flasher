#!/usr/bin/env python3
"""Print a PIT file as a table: partition id, offset, size, name and the image it takes."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "flasher"))
from odin_flash import BLOCK_BYTES, parse_pit  # noqa: E402


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: pit_info.py FILE.pit")
    with open(sys.argv[1], "rb") as f:
        entries = parse_pit(f.read())
    print(f"{'id':>3}  {'offset':>9}  {'size':>10}  {'partition':<14} image")
    for entry in entries:
        size = f"{entry['blocks'] * BLOCK_BYTES / 2**20:.1f} MiB" if entry["blocks"] else "-"
        print(f"{entry['id']:>3}  {entry['offset']:>9}  {size:>10}  {entry['partition']:<14} {entry['file']}")
    print(f"{len(entries)} partitions")


if __name__ == "__main__":
    main()
