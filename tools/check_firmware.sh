#!/bin/bash
# Check each .tar.md5 in a firmware folder against the checksum stored at its end.
set -u
cd "${1:?usage: check_firmware.sh FIRMWARE_FOLDER}" || exit 1
bad=0
for f in *.tar.md5; do
  line=$(tail -c 200 "$f" | tail -n1)
  want=$(echo "$line" | cut -d' ' -f1)
  have=$(head -c -"$(echo "$line" | wc -c)" "$f" | md5sum | cut -d' ' -f1)
  if [ "$want" = "$have" ]; then echo "OK   $f"; else echo "BAD  $f"; bad=1; fi
done
exit "$bad"
