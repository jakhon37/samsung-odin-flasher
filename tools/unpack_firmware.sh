#!/bin/bash
# Unpack BL, AP, CP and CSC into one folder of plain images. HOME_CSC is left out on purpose.
set -eu
firmware="${1:?usage: unpack_firmware.sh FIRMWARE_FOLDER OUTPUT_FOLDER}"
output="${2:?usage: unpack_firmware.sh FIRMWARE_FOLDER OUTPUT_FOLDER}"
mkdir -p "$output"
for prefix in BL AP CP CSC; do
  for f in "$firmware"/"$prefix"_*.tar.md5; do
    [ -e "$f" ] || continue
    echo "unpacking $(basename "$f")"
    tar -xf "$f" --exclude='meta-data*' -C "$output"
  done
done
cd "$output"
lz4 -dm --rm ./*.lz4
ls -l
