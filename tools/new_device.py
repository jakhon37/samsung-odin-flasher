#!/usr/bin/env python3
"""Create a device folder (device.json + device.pit) for a phone from its firmware and partition table.

Images are listed in the order they appear in the BL, AP, CP and CSC tars, which is Odin's order.
Tar entries are matched to the phone's PIT by file name, ignoring a trailing .lz4.
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
import tarfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "flasher"))
from odin_flash import parse_pit  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def tar_order(firmware):
    """File names in flash order, from the firmware's tars. HOME_CSC is left out on purpose."""
    names = []
    for prefix in ("BL", "AP", "CP", "CSC"):
        for path in sorted(glob.glob(os.path.join(firmware, f"{prefix}_*.tar.md5"))):
            with tarfile.open(path, "r:") as tar:
                for member in tar:
                    name = member.name.removesuffix(".lz4")
                    if member.isfile() and "/" not in name and name not in names:
                        names.append(name)
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="exact model, such as SM-A102N")
    parser.add_argument("--name", required=True, help="marketing name, such as 'Samsung Galaxy A10e'")
    parser.add_argument("--version", required=True, help="firmware version, such as A102NKOS3CWD1")
    parser.add_argument("--firmware", required=True, help="folder with the BL, AP, CP and CSC .tar.md5 files")
    parser.add_argument("--images", required=True, help="folder of unpacked images")
    parser.add_argument("--pit", required=True, help="partition table read from this phone (--dump-pit)")
    parser.add_argument("--out", required=True, help="device folder to create")
    args = parser.parse_args()

    with open(args.pit, "rb") as f:
        entries = {entry["file"]: entry for entry in parse_pit(f.read()) if entry["file"]}
    images, skipped = [], []
    for name in tar_order(args.firmware):
        path = os.path.join(args.images, name)
        if name in entries and os.path.exists(path):
            images.append({"file": name, "partition": entries[name]["partition"], "sha256": sha256(path)})
        else:
            skipped.append(name)
    if not images:
        raise SystemExit("no firmware file matches this partition table: is this firmware for this phone?")

    os.makedirs(args.out, exist_ok=True)
    device = {"model": args.model, "name": args.name, "firmware": args.version, "images": images}
    with open(os.path.join(args.out, "device.json"), "w") as f:
        json.dump(device, f, indent=2)
        f.write("\n")
    shutil.copyfile(args.pit, os.path.join(args.out, "device.pit"))
    for image in images:
        print(f"{image['file']:20} -> {image['partition']}")
    print(f"{len(images)} images written to {args.out}/device.json")
    if skipped:
        print("Not flashed, because no PIT entry or unpacked file matches: " + ", ".join(skipped))


if __name__ == "__main__":
    main()
