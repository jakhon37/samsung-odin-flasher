"""Send one zero-length packet to the phone and report what it answers. Writes nothing to storage."""
import ctypes
import errno
import fcntl
import glob
import os
import struct

USBDEVFS_BULK = 0xC0185502
USBDEVFS_CLAIMINTERFACE = 0x8004550F
USBDEVFS_RELEASEINTERFACE = 0x80045510
# Check these with: lsusb -v -d 04e8:685d
INTERFACE, READ_EP, WRITE_EP = 1, 0x81, 0x02


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
buf = ctypes.create_string_buffer(4096)


def bulk(endpoint, length, timeout):
    arg = struct.pack("IIIIQ", endpoint, length, timeout, 0, ctypes.addressof(buf))
    return fcntl.ioctl(fd, USBDEVFS_BULK, ctypes.create_string_buffer(arg, len(arg)))


try:
    print("zero-length packet sent, result", bulk(WRITE_EP, 0, 2000), flush=True)
except OSError as e:
    print("zero-length send failed:", errno.errorcode.get(e.errno, e.errno), flush=True)
for attempt in range(2):
    try:
        got = bulk(READ_EP, len(buf), 8000)
    except OSError as e:
        print("read:", errno.errorcode.get(e.errno, e.errno), flush=True)
        continue
    data = buf.raw[:got]
    ints = struct.unpack(f"<{got // 4}i", data[: got // 4 * 4])[:4] if got >= 4 else ()
    print(f"got {got} bytes: hex={data[:32].hex()} ints={ints}", flush=True)
    break
fcntl.ioctl(fd, USBDEVFS_RELEASEINTERFACE, iface)
os.close(fd)
