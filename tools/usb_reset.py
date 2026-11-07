"""Send a USB port reset to the phone (USBDEVFS_RESET). Writes nothing to the phone's storage."""
import fcntl
import glob
import os
import struct

USBDEVFS_RESET = 0x5514

for path in glob.glob("/dev/bus/usb/*/*"):
    try:
        with open(path, "rb") as f:
            desc = f.read(18)
    except OSError:
        continue
    vendor, product = struct.unpack("<HH", desc[8:12])
    if (vendor, product) == (0x04E8, 0x685D):
        fd = os.open(path, os.O_RDWR)
        try:
            fcntl.ioctl(fd, USBDEVFS_RESET, 0)
            print("reset sent to", path)
        finally:
            os.close(fd)
