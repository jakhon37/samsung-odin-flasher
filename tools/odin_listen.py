"""Listen on the phone's bulk IN endpoint for a pending reply. Sends nothing to the phone."""
import ctypes
import errno
import fcntl
import glob
import os
import struct
import time

USBDEVFS_BULK = 0xC0185502
USBDEVFS_CLAIMINTERFACE = 0x8004550F
USBDEVFS_RELEASEINTERFACE = 0x80045510
# Check these with: lsusb -v -d 04e8:685d
INTERFACE, READ_EP = 1, 0x81


def find_phone():
    for path in glob.glob("/dev/bus/usb/*/*"):
        try:
            with open(path, "rb") as f:
                desc = f.read(18)
        except OSError:
            continue
        if struct.unpack("<HH", desc[8:12]) == (0x04E8, 0x685D):
            return path
    raise SystemExit("phone not found")


path = find_phone()
fd = os.open(path, os.O_RDWR)
iface = struct.pack("I", INTERFACE)
fcntl.ioctl(fd, USBDEVFS_CLAIMINTERFACE, iface)
print("listening on", path, flush=True)
buf = ctypes.create_string_buffer(4096)
start = time.time()
total = 0
while time.time() - start < 25:
    arg = struct.pack("IIIIQ", READ_EP, len(buf), 5000, 0, ctypes.addressof(buf))
    mutable = ctypes.create_string_buffer(arg, len(arg))
    try:
        got = fcntl.ioctl(fd, USBDEVFS_BULK, mutable)
    except OSError as e:
        print(f"{time.time() - start:5.1f}s read: {errno.errorcode.get(e.errno, e.errno)}", flush=True)
        if e.errno != errno.ETIMEDOUT:
            break
        continue
    total += got
    data = buf.raw[:got]
    ints = struct.unpack(f"<{got // 4}i", data[: got // 4 * 4])[:6] if got >= 4 else ()
    print(f"{time.time() - start:5.1f}s got {got} bytes: hex={data[:32].hex()} ints={ints} ascii={data[:16]!r}", flush=True)
fcntl.ioctl(fd, USBDEVFS_RELEASEINTERFACE, iface)
os.close(fd)
print("total bytes received:", total)
