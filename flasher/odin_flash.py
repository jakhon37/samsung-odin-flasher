#!/usr/bin/env python3
"""Flash stock firmware to a Samsung phone in Download mode, using only Python and Linux usbfs.

Speaks Samsung's Odin protocol directly, including the zero-length packets some bootloaders need.
Each phone is described by a device folder holding device.json and device.pit.

Stops on the first error and never resends data that reached the phone.
Exit codes: 0 finished, 2 stopped before anything was written, 3 stopped after writing began.
"""
import argparse
import ctypes
import errno
import fcntl
import glob
import hashlib
import json
import os
import struct
import subprocess
import sys
import time

SAMSUNG_VENDOR = 0x04E8
DOWNLOAD_PRODUCTS = (0x685D, 0x6601, 0x68C3)

PART_SIZE = 1024 * 1024
PARTS_PER_SEQUENCE = 30
COMMAND_SIZE = 1024
PIT_BLOCK = 500
BLOCK_BYTES = 512
REPLY_TIMEOUT = 5000
WRITE_TIMEOUT = 60000
ZLP_TIMEOUT = 5000
PART_ACK_TIMEOUT = 10000
PART_ACK_FLUSHED_TIMEOUT = 30000
SEQUENCE_END_TIMEOUT = 180000
ERROR_NAMES = {-7: "Ext4", -6: "Size", -5: "Auth", -4: "Write", -3: "Erase", -2: "Write protect"}
# usbfs needs one contiguous kernel buffer per transfer, and 1 MiB can fail with ENOMEM mid-flash.
# Whole-packet chunks stream identically to the phone, since only a short packet ends a transfer.
USB_CHUNK = 64 * 1024
ENOMEM_RETRIES = 40
ENOMEM_WAIT = 0.25


def say(text):
    print(f"{time.strftime('%H:%M:%S')} {text}", flush=True)


class Stop(Exception):
    pass


def find_endpoints(descriptors):
    """Return (interface, bulk IN, bulk OUT) of the CDC data interface in raw USB descriptors."""
    interface = klass = None
    bulk_in = bulk_out = None
    i = 0
    while i + 1 < len(descriptors) and descriptors[i] != 0:
        length, kind = descriptors[i], descriptors[i + 1]
        if kind == 4:
            interface, klass = descriptors[i + 2], descriptors[i + 5]
            bulk_in = bulk_out = None
        elif kind == 5 and klass == 0x0A and descriptors[i + 3] & 3 == 2:
            address = descriptors[i + 2]
            if address & 0x80:
                bulk_in = address
            else:
                bulk_out = address
            if bulk_in is not None and bulk_out is not None:
                return interface, bulk_in, bulk_out
        i += length
    raise Stop("no CDC data interface with bulk endpoints on this device")


class UsbTransport:
    USBDEVFS_BULK = 0xC0185502
    USBDEVFS_CLAIMINTERFACE = 0x8004550F
    USBDEVFS_RELEASEINTERFACE = 0x80045510

    def __init__(self):
        path = descriptors = None
        for candidate in glob.glob("/dev/bus/usb/*/*"):
            try:
                with open(candidate, "rb") as f:
                    data = f.read(4096)
            except OSError:
                continue
            vendor, product = struct.unpack("<HH", data[8:12])
            if vendor == SAMSUNG_VENDOR and product in DOWNLOAD_PRODUCTS:
                path, descriptors = candidate, data
        if path is None:
            raise Stop("phone not found on USB, or no permission to open it")
        self.interface, self.read_ep, self.write_ep = find_endpoints(descriptors)
        self.fd = os.open(path, os.O_RDWR)
        self.iface = struct.pack("I", self.interface)
        fcntl.ioctl(self.fd, self.USBDEVFS_CLAIMINTERFACE, self.iface)
        self.out_buf = ctypes.create_string_buffer(USB_CHUNK)
        self.in_buf = ctypes.create_string_buffer(4096)
        say(f"claimed {path}, interface {self.interface}, IN {self.read_ep:#04x}, OUT {self.write_ep:#04x}")

    def _bulk(self, endpoint, length, timeout, buffer):
        arg = struct.pack("IIIIQ", endpoint, length, timeout, 0, ctypes.addressof(buffer))
        return fcntl.ioctl(self.fd, self.USBDEVFS_BULK, ctypes.create_string_buffer(arg, len(arg)))

    def write(self, data, timeout):
        ctypes.memmove(self.out_buf, data, len(data))
        return self._bulk(self.write_ep, len(data), timeout, self.out_buf)

    def read(self, length, timeout):
        got = self._bulk(self.read_ep, length, timeout, self.in_buf)
        return self.in_buf.raw[:got]

    def close(self):
        fcntl.ioctl(self.fd, self.USBDEVFS_RELEASEINTERFACE, self.iface)
        os.close(self.fd)


def parse_pit(pit):
    """Return the PIT's entries as a list of dicts, in table order."""
    magic, count = struct.unpack("<II", pit[:8])
    if magic != 0x12349876:
        raise Stop(f"bad PIT magic {magic:#x}")
    entries = []
    for i in range(count):
        fields = struct.unpack("<9i32s32s32s", pit[28 + i * 132: 28 + (i + 1) * 132])
        entries.append({
            "binary": fields[0], "device": fields[1], "id": fields[2], "offset": fields[5], "blocks": fields[6],
            "partition": fields[9].split(b"\0")[0].decode(),
            "file": fields[10].split(b"\0")[0].decode(),
        })
    return entries


def load_device(folder):
    """Read a device folder. Returns (model, reference PIT bytes, [(file, partition, sha256), ...])."""
    with open(os.path.join(folder, "device.json")) as f:
        device = json.load(f)
    with open(os.path.join(folder, "device.pit"), "rb") as f:
        pit = f.read()
    return device["model"], pit, [(i["file"], i["partition"], i["sha256"]) for i in device["images"]]


class Flasher:
    def __init__(self, transport, img_dir, reference_pit, images):
        self.usb = transport
        self.img_dir = img_dir
        self.reference_pit = reference_pit
        self.images = images
        self.writing = False
        self.where = "start"

    def send_bytes(self, data, timeout):
        """Send in chunks. ENOMEM fails before anything reaches the USB bus, so only it is retried."""
        sent = 0
        while sent < len(data):
            chunk = data[sent:sent + USB_CHUNK]
            for attempt in range(ENOMEM_RETRIES + 1):
                try:
                    done = self.usb.write(chunk, timeout)
                    break
                except OSError as e:
                    if e.errno != errno.ENOMEM or attempt == ENOMEM_RETRIES:
                        raise Stop(f"{self.where}: USB write at byte {sent}: {errno.errorcode.get(e.errno, e.errno)}")
                    time.sleep(ENOMEM_WAIT)
            if done != len(chunk):
                raise Stop(f"{self.where}: USB wrote {done} of {len(chunk)} bytes")
            sent += done
        return sent

    def zlp(self):
        try:
            self.usb.write(b"", ZLP_TIMEOUT)
        except OSError as e:
            say(f"warning: empty packet: {errno.errorcode.get(e.errno, e.errno)}")

    def send_command(self, words, terminate=True, wide_at_8=None):
        packet = struct.pack(f"<{len(words)}i", *words)
        if wide_at_8 is not None:
            packet = packet[:8] + struct.pack("<q", wide_at_8)
        sent = self.send_bytes(packet.ljust(COMMAND_SIZE, b"\0"), REPLY_TIMEOUT)
        if sent != COMMAND_SIZE:
            raise Stop(f"short command write: {sent}")
        if terminate:
            self.zlp()

    def reply(self, expected_type, what, timeout=REPLY_TIMEOUT):
        try:
            data = self.usb.read(8, timeout)
        except OSError as e:
            raise Stop(f"{what}: no reply ({errno.errorcode.get(e.errno, e.errno)})")
        if len(data) != 8:
            raise Stop(f"{what}: reply was {len(data)} bytes: {data.hex()}")
        kind, value = struct.unpack("<ii", data)
        if data[0] == 0xFF:
            raise Stop(f"{what}: phone refused, code {value} ({ERROR_NAMES.get(value, 'unknown')})")
        if kind != expected_type:
            raise Stop(f"{what}: unexpected reply {data.hex()}")
        return value

    def begin_session(self):
        """Handshake, then session setup. Empty packets start only once the part size is set."""
        if self.usb.write(b"ODIN", REPLY_TIMEOUT) != 4:
            raise Stop("handshake write failed")
        try:
            answer = self.usb.read(4, REPLY_TIMEOUT)
        except OSError as e:
            raise Stop(f"handshake: no reply ({errno.errorcode.get(e.errno, e.errno)})")
        if answer != b"LOKE":
            raise Stop(f"handshake: got {answer!r}")
        self.send_command([0x64, 0, 0x7FFFFFFF], terminate=False)
        version = self.reply(0x64, "begin session")
        say(f"session begun, bootloader version {version:#010x}")
        if version >> 16 < 2:
            raise Stop("this bootloader uses an older protocol version, which this tool doesn't support")
        self.send_command([0x64, 5, PART_SIZE], terminate=False)
        if self.reply(0x64, "set part size") != 0:
            raise Stop("phone rejected the part size")

    def read_pit(self):
        self.send_command([0x65, 1])
        size = self.reply(0x65, "PIT request")
        pit = b""
        for index in range((size + PIT_BLOCK - 1) // PIT_BLOCK):
            self.send_command([0x65, 2, index])
            try:
                pit += self.usb.read(PIT_BLOCK, REPLY_TIMEOUT)
            except OSError as e:
                raise Stop(f"PIT block {index}: {errno.errorcode.get(e.errno, e.errno)}")
        try:
            self.usb.read(0, 200)
        except OSError:
            pass
        self.send_command([0x65, 3])
        self.reply(0x65, "PIT end")
        return pit[:size]

    def plan(self, pit):
        """Match each image to the phone's own PIT entry; any doubt stops the flash."""
        if pit != self.reference_pit:
            raise Stop("phone's partition table differs from the verified copy")
        entries = {entry["file"]: entry for entry in parse_pit(pit) if entry["file"]}
        plan = []
        for filename, partition, _ in self.images:
            entry = entries.get(filename)
            if entry is None or entry["partition"] != partition:
                raise Stop(f"{filename}: PIT entry {entry} does not match {partition}")
            size = os.path.getsize(os.path.join(self.img_dir, filename))
            if entry["blocks"] and size > entry["blocks"] * BLOCK_BYTES:
                raise Stop(f"{filename}: {size} bytes does not fit {partition}")
            plan.append((filename, entry, size))
        return plan

    def check_hashes(self):
        for filename, _, sha256 in self.images:
            digest = hashlib.sha256()
            with open(os.path.join(self.img_dir, filename), "rb") as f:
                while chunk := f.read(8 * PART_SIZE):
                    digest.update(chunk)
            if digest.hexdigest() != sha256:
                raise Stop(f"{filename}: hash differs from the factory image")
        say(f"all {len(self.images)} image hashes match the factory firmware")

    def send_part(self, data, index, what):
        self.writing = True
        self.where = f"{what} part {index}"
        sent = self.send_bytes(data.ljust(PART_SIZE, b"\0"), WRITE_TIMEOUT)
        if sent != PART_SIZE:
            raise Stop(f"{what} part {index}: wrote {sent} of {PART_SIZE}")
        try:
            answer = self.usb.read(8, PART_ACK_TIMEOUT)
        except OSError as e:
            if e.errno != errno.ETIMEDOUT:
                raise Stop(f"{what} part {index}: {errno.errorcode.get(e.errno, e.errno)}")
            say(f"{what} part {index}: no ack yet, sending an empty packet")
            self.zlp()
            try:
                answer = self.usb.read(8, PART_ACK_FLUSHED_TIMEOUT)
            except OSError as e2:
                raise Stop(f"{what} part {index}: no ack ({errno.errorcode.get(e2.errno, e2.errno)})")
        if len(answer) != 8 or answer[0] == 0xFF:
            raise Stop(f"{what} part {index}: bad ack {answer.hex()}")
        acked = struct.unpack("<i", answer[4:])[0]
        if acked != index:
            raise Stop(f"{what}: phone acked part {acked}, expected {index}")

    def flash_image(self, filename, entry, size, sha256):
        what = entry["partition"]
        started = time.time()
        sequence_bytes = PART_SIZE * PARTS_PER_SEQUENCE
        sequences = (size + sequence_bytes - 1) // sequence_bytes
        say(f"{what}: starting, {size} bytes in {sequences} sequences")
        self.send_command([0x66, 0])
        self.reply(0x66, f"{what} request flash")
        digest = hashlib.sha256()
        sent_total = 0
        with open(os.path.join(self.img_dir, filename), "rb") as f:
            for sequence in range(sequences):
                real = min(sequence_bytes, size - sent_total)
                parts = (real + PART_SIZE - 1) // PART_SIZE
                self.send_command([0x66, 2, parts * PART_SIZE])
                self.reply(0x66, f"{what} sequence {sequence} start")
                for index in range(parts):
                    data = f.read(PART_SIZE)
                    digest.update(data)
                    self.send_part(data, index, f"{what} sequence {sequence}")
                sent_total += real
                last = sequence + 1 == sequences
                if last and digest.hexdigest() != sha256:
                    raise Stop(f"{what}: bytes read differ from the factory image, not finishing it")
                self.send_command([0x66, 3, 0, real, entry["binary"], entry["device"], entry["id"], int(last), 0, 0])
                self.reply(0x66, f"{what} sequence {sequence} end", SEQUENCE_END_TIMEOUT)
                if sequences > 10 and (sequence + 1) % 20 == 0:
                    say(f"{what}: {sequence + 1}/{sequences} sequences, {int(time.time() - started)}s")
        say(f"{what}: done in {int(time.time() - started)}s")

    def run(self, resume, start_from=None):
        if resume:
            say("continuing the session already open on the phone")
        else:
            self.begin_session()
        pit = self.read_pit()
        plan = self.plan(pit)
        say(f"partition table matches; {len(plan)} images mapped")
        for filename, entry, size in plan:
            say(f"  {filename:18} -> {entry['partition']:12} id {entry['id']:>3} {size:>11} bytes")
        self.check_hashes()
        if start_from is not None:
            names = [entry["partition"] for _, entry, _ in plan]
            if start_from not in names:
                raise Stop(f"{start_from} is not in the flash list")
            plan = plan[names.index(start_from):]
            say(f"starting at {start_from}: {len(plan)} images left, skipping the {len(names) - len(plan)} already accepted")
        total = sum(size for _, _, size in plan)
        self.send_command([0x64, 2], wide_at_8=total)
        self.reply(0x64, "total size")
        say(f"total {total} bytes accepted; writing starts now")
        hashes = {name: sha256 for name, _, sha256 in self.images}
        started = time.time()
        for number, (filename, entry, size) in enumerate(plan, 1):
            say(f"--- image {number}/{len(plan)}")
            self.flash_image(filename, entry, size, hashes[filename])
        say(f"all images flashed in {int(time.time() - started)}s, ending session")
        self.send_command([0x67, 0])
        self.reply(0x67, "end session")
        self.send_command([0x67, 1])
        try:
            self.reply(0x67, "reboot")
        except Stop as e:
            say(f"reboot reply not seen, the phone may already be restarting: {e}")
        say("reboot requested")


def preflight():
    phones = subprocess.run(["lsusb", "-d", "04e8:"], capture_output=True, text=True).stdout.strip().splitlines()
    wanted = [f"04e8:{product:04x}" for product in DOWNLOAD_PRODUCTS]
    if len(phones) != 1 or not any(usb_id in phones[0] for usb_id in wanted):
        raise Stop(f"expected one phone in Download mode, saw {phones}")
    for tool in ("heimdall", "Thor-Linux"):
        if subprocess.run(["pgrep", "-x", tool], capture_output=True).returncode == 0:
            raise Stop(f"{tool} is running")
    say(f"phone: {phones[0]}")


def confirm(model, partial):
    """Ask before erasing. The phone's model is typed back so a wrong folder is noticed."""
    what = "continue flashing" if partial else "ERASE the phone and flash it"
    answer = input(f"Type the phone's model ({model}) to {what}: ")
    if answer.strip() != model:
        raise Stop("not confirmed")


def main():
    parser = argparse.ArgumentParser(description="Flash stock firmware to a Samsung phone in Download mode.")
    parser.add_argument("--device", help="device folder holding device.json and device.pit")
    parser.add_argument("--images", help="folder of unpacked firmware images")
    session = parser.add_mutually_exclusive_group(required=True)
    session.add_argument("--fresh", action="store_true", help="start a new session (phone freshly restarted)")
    session.add_argument("--resume", action="store_true", help="use a session already open, with no image in progress")
    parser.add_argument("--from", dest="start_from", metavar="PARTITION", help="skip images before this partition")
    parser.add_argument("--dump-pit", metavar="FILE", help="save the phone's partition table and write nothing else")
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    args = parser.parse_args()
    if not args.dump_pit and not (args.device and args.images):
        parser.error("--device and --images are needed to flash")

    flasher = None
    try:
        preflight()
        if args.dump_pit:
            transport = UsbTransport()
            flasher = Flasher(transport, None, None, [])
            try:
                if args.fresh:
                    flasher.begin_session()
                pit = flasher.read_pit()
            finally:
                transport.close()
            with open(args.dump_pit, "wb") as f:
                f.write(pit)
            say(f"saved {len(pit)} bytes to {args.dump_pit}. The session is still open: use --resume, or force-restart.")
            return
        model, reference_pit, images = load_device(args.device)
        if not args.yes:
            confirm(model, args.start_from is not None)
        transport = UsbTransport()
        flasher = Flasher(transport, args.images, reference_pit, images)
        try:
            flasher.run(args.resume, args.start_from)
        finally:
            transport.close()
    except (Stop, OSError, EOFError) as e:
        wrote = flasher is not None and flasher.writing
        where = f" at {flasher.where}" if flasher is not None else ""
        say(f"STOPPED {'AFTER WRITING BEGAN' if wrote else 'BEFORE ANY WRITE'}{where}: {e}")
        sys.exit(3 if wrote else 2)
    say("DONE")


if __name__ == "__main__":
    main()
