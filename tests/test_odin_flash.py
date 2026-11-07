#!/usr/bin/env python3
"""Test odin_flash.py against a simulated phone. Never touches a real phone.

The simulation behaves as measured on an SM-A102N: after the part size is set, a 1024-byte command
does nothing until a zero-length packet follows.

    python3 tests/test_odin_flash.py                 # about a second
    python3 tests/test_odin_flash.py firmware/img    # also runs the real images through it
"""
import errno
import hashlib
import json
import os
import struct
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "flasher"))
import odin_flash as of  # noqa: E402

MIB = of.PART_SIZE
DEVICE = os.path.join(ROOT, "devices", "sm-a102n")
MODEL, REAL_PIT, REAL_IMAGES = of.load_device(DEVICE)


class FakePhone:
    def __init__(self, pit=REAL_PIT, session_open=False, fail=None, ack_needs_zlp=False):
        self.pit = pit
        self.part_mode = session_open
        self.fail = fail or {}
        self.ack_needs_zlp = ack_needs_zlp
        self.replies = []
        self.pending = None
        self.parts_left = 0
        self.seq_parts = 0
        self.held_ack = None
        self.partition_hash = hashlib.sha256()
        self.partition_size = 0
        self.sequence = bytearray()
        self.hashes = {}
        self.sizes = {}
        self.parts_received = 0
        self.part_fill = 0
        self.writes = 0
        self.total = None
        self.ended = self.rebooted = False

    def reply(self, kind, value=0):
        self.replies.append(struct.pack("<ii", kind, value))

    def write(self, data, timeout):
        if not data and self.held_ack is not None:
            self.replies.append(self.held_ack)
            self.held_ack = None
            return 0
        if self.parts_left:
            if not data:
                assert self.fail.get("silent_part"), "stray empty packet inside a file part stream"
                return 0
            assert len(data) % 512 == 0 and len(data) <= of.USB_CHUNK, f"chunk of {len(data)} bytes"
            self.writes += 1
            every = self.fail.get("enomem_every")
            if self.fail.get("enomem_always") or (every and self.writes % every == 0):
                raise OSError(errno.ENOMEM, "simulated allocation failure")
            self.sequence.extend(data)
            self.part_fill += len(data)
            if self.part_fill < MIB:
                return len(data)
            assert self.part_fill == MIB, f"part overran to {self.part_fill}"
            self.part_fill = 0
            self.parts_received += 1
            index = self.seq_parts - self.parts_left
            self.parts_left -= 1
            if self.fail.get("silent_part") == self.parts_received:
                return len(data)
            ack = struct.pack("<ii", 0, index)
            if self.ack_needs_zlp:
                self.held_ack = ack
            else:
                self.replies.append(ack)
            return len(data)
        if data == b"ODIN":
            self.replies.append(b"LOKE")
            return 4
        if not data:
            if self.pending is not None:
                command, self.pending = self.pending, None
                self.process(command)
            return 0
        assert len(data) == 1024, f"command of {len(data)} bytes"
        if self.part_mode:
            self.pending = bytes(data)
        else:
            self.process(bytes(data))
        return len(data)

    def process(self, cmd):
        a, b = struct.unpack("<ii", cmd[:8])
        if a == 0x64 and b == 0:
            self.reply(0x64, self.fail.get("version", 0x00030000))
        elif a == 0x64 and b == 5:
            assert struct.unpack("<i", cmd[8:12])[0] == MIB
            self.part_mode = True
            self.reply(0x64)
        elif a == 0x64 and b == 2:
            self.total = struct.unpack("<q", cmd[8:16])[0]
            self.reply(0x64)
        elif a == 0x65 and b == 1:
            self.reply(0x65, len(self.pit))
        elif a == 0x65 and b == 2:
            index = struct.unpack("<i", cmd[8:12])[0]
            self.replies.append(self.pit[index * 500:(index + 1) * 500])
        elif a == 0x65 and b == 3:
            self.reply(0x65)
        elif a == 0x66 and b == 0:
            assert self.total is not None, "flash before total bytes"
            self.partition_hash = hashlib.sha256()
            self.partition_size = 0
            self.reply(0x66)
        elif a == 0x66 and b == 2:
            aligned = struct.unpack("<i", cmd[8:12])[0]
            assert aligned % MIB == 0 and 0 < aligned <= 30 * MIB
            self.parts_left = self.seq_parts = aligned // MIB
            self.sequence = bytearray()
            self.reply(0x66)
        elif a == 0x66 and b == 3:
            dest, real, binary, device, pid, last, efs, bootloader = struct.unpack("<8i", cmd[8:40])
            assert dest == 0 and binary == 0 and device == 2 and efs == 0 and bootloader == 0
            assert self.parts_left == 0 and real <= len(self.sequence)
            assert not any(self.sequence[real:]), "padding was not zero"
            if self.fail.get("refuse_id") == pid:
                self.replies.append(struct.pack("<ii", -1, -5))
                return
            self.partition_hash.update(self.sequence[:real])
            self.partition_size += real
            if last:
                self.hashes[pid] = self.partition_hash.hexdigest()
                self.sizes[pid] = self.partition_size
            self.reply(0x66)
        elif a == 0x67 and b == 0:
            self.ended = True
            self.reply(0x67)
        elif a == 0x67 and b == 1:
            self.rebooted = True
            self.reply(0x67)
        else:
            raise AssertionError(f"unknown command {a:#x}/{b}")

    def read(self, length, timeout):
        if not self.replies:
            raise OSError(errno.ETIMEDOUT, "simulated timeout")
        data = self.replies.pop(0)
        if length and len(data) > length:
            raise OSError(errno.EOVERFLOW, "simulated overflow")
        return data


def small_images(folder):
    """Small images whose sizes hit the padding edge cases."""
    images = []
    sizes = {"sboot.bin": 3 * MIB + 17, "param.bin": MIB, "cm.bin": 1, "vbmeta.img": 9104,
             "boot.img": 30 * MIB + 1, "recovery.img": 30 * MIB}
    for filename, partition, _ in REAL_IMAGES[:6]:
        data = os.urandom(1024) * (sizes[filename] // 1024) + os.urandom(sizes[filename] % 1024)
        with open(os.path.join(folder, filename), "wb") as f:
            f.write(data)
        images.append((filename, partition, hashlib.sha256(data).hexdigest()))
    return images


def flasher(phone, folder, images):
    return of.Flasher(phone, folder, REAL_PIT, images)


def expect_stop(run, needle, want_writing, instance):
    try:
        run()
    except of.Stop as e:
        assert needle in str(e), f"stopped for the wrong reason: {e}"
        assert instance.writing == want_writing, f"writing flag {instance.writing}"
        print(f"PASS stop: {e}")
        return
    raise AssertionError(f"did not stop, wanted {needle}")


def test_endpoint_detection():
    # Device, config, control interface with an interrupt endpoint, then the data interface.
    descriptors = bytes([18, 1]) + bytes(16)
    descriptors += bytes([9, 2]) + bytes(7)
    descriptors += bytes([9, 4, 0, 0, 1, 2, 2, 1, 0]) + bytes([5, 0x24, 0, 16, 1])
    descriptors += bytes([7, 5, 0x83, 3, 16, 0, 9])
    descriptors += bytes([9, 4, 1, 0, 2, 0x0A, 0, 0, 0])
    a10e = descriptors + bytes([7, 5, 0x81, 2, 0, 2, 0, 7, 5, 0x02, 2, 0, 2, 0])
    a32 = descriptors + bytes([7, 5, 0x81, 2, 0, 2, 0, 7, 5, 0x01, 2, 0, 2, 0])
    assert of.find_endpoints(a10e) == (1, 0x81, 0x02)
    assert of.find_endpoints(a32) == (1, 0x81, 0x01)
    try:
        of.find_endpoints(descriptors)
        raise AssertionError("a device with no bulk endpoints was accepted")
    except of.Stop:
        pass
    print("PASS USB endpoints detected, including a phone with a different OUT endpoint")


def test_pit_and_profile():
    entries = of.parse_pit(REAL_PIT)
    assert len(entries) == 38 and entries[0]["partition"] == "BOOTLOADER" and entries[-1]["partition"] == "USERDATA"
    with open(os.path.join(DEVICE, "device.json")) as f:
        profile = json.load(f)
    assert profile["model"] == "SM-A102N" and len(profile["images"]) == 16
    print("PASS partition table and device profile load")


def test_flash_behaviour():
    with tempfile.TemporaryDirectory() as folder:
        images = small_images(folder)
        ids = {"sboot.bin": 80, "param.bin": 12, "cm.bin": 7, "vbmeta.img": 22, "boot.img": 15, "recovery.img": 16}

        for resume in (True, False):
            phone = FakePhone(session_open=resume)
            flasher(phone, folder, images).run(resume)
            for filename, _, digest in images:
                assert phone.hashes[ids[filename]] == digest, filename
            assert phone.ended and phone.rebooted
            assert phone.total == sum(os.path.getsize(os.path.join(folder, i[0])) for i in images)
            print(f"PASS small images flashed byte-exact (resume={resume})")

        phone = FakePhone(session_open=True, ack_needs_zlp=True)
        flasher(phone, folder, images[:3]).run(True)
        assert phone.rebooted
        print("PASS missing part ack recovered with an empty packet")

        phone = FakePhone(session_open=True)
        instance = flasher(phone, folder, images)
        instance.zlp = lambda: None
        expect_stop(lambda: instance.run(True), "PIT request: no reply", False, instance)

        bad_pit = bytearray(REAL_PIT)
        bad_pit[100] ^= 1
        phone = FakePhone(pit=bytes(bad_pit), session_open=True)
        instance = flasher(phone, folder, images)
        expect_stop(lambda: instance.run(True), "differs from the verified copy", False, instance)
        assert phone.parts_received == 0 and phone.total is None
        print("PASS different partition table wrote nothing")

        phone = FakePhone(fail={"version": 0x00010000})
        instance = flasher(phone, folder, images)
        expect_stop(lambda: instance.run(False), "older protocol", False, instance)
        print("PASS older protocol version refused")

        tampered = [(images[0][0], images[0][1], "0" * 64)] + images[1:]
        phone = FakePhone(session_open=True)
        instance = flasher(phone, folder, tampered)
        expect_stop(lambda: instance.run(True), "hash differs", False, instance)
        assert phone.parts_received == 0
        print("PASS wrong image hash wrote nothing")

        phone = FakePhone(session_open=True, fail={"refuse_id": 22})
        instance = flasher(phone, folder, images)
        expect_stop(lambda: instance.run(True), "Auth", True, instance)
        assert 15 not in phone.hashes and not phone.ended
        print("PASS refusal stopped before the next partition")

        of.ENOMEM_WAIT = 0
        phone = FakePhone(session_open=True, fail={"enomem_every": 3})
        flasher(phone, folder, images).run(True)
        for filename, _, digest in images:
            assert phone.hashes[ids[filename]] == digest, filename
        print("PASS repeated allocation errors retried, images still byte-exact")

        phone = FakePhone(session_open=True, fail={"enomem_always": True})
        instance = flasher(phone, folder, images)
        expect_stop(lambda: instance.run(True), "ENOMEM", True, instance)
        assert phone.parts_received == 0 and not phone.ended
        print("PASS persistent allocation error stopped")

        phone = FakePhone()
        flasher(phone, folder, images).run(False, "BOOT")
        assert set(phone.hashes) == {15, 16} and phone.rebooted
        sizes = [os.path.getsize(os.path.join(folder, n)) for n in ("boot.img", "recovery.img")]
        assert phone.total == sum(sizes)
        print("PASS start point skips earlier partitions and sends the right total")

        instance = flasher(FakePhone(session_open=True), folder, images)
        expect_stop(lambda: instance.run(True, "NOPE"), "not in the flash list", False, instance)

        part_ack, flushed = of.PART_ACK_TIMEOUT, of.PART_ACK_FLUSHED_TIMEOUT
        of.PART_ACK_TIMEOUT = of.PART_ACK_FLUSHED_TIMEOUT = 1
        phone = FakePhone(session_open=True, fail={"silent_part": 2})
        instance = flasher(phone, folder, images)
        expect_stop(lambda: instance.run(True), "no ack", True, instance)
        assert phone.parts_received == 2 and not phone.ended
        of.PART_ACK_TIMEOUT, of.PART_ACK_FLUSHED_TIMEOUT = part_ack, flushed
        print("PASS silence stopped with no resend")


def test_real_images(folder):
    phone = FakePhone()
    flasher(phone, folder, REAL_IMAGES).run(False)
    assert phone.rebooted and phone.ended and len(phone.hashes) == len(REAL_IMAGES)
    entries = {entry["file"]: entry for entry in of.parse_pit(REAL_PIT)}
    for filename, _, digest in REAL_IMAGES:
        pid = entries[filename]["id"]
        assert phone.hashes[pid] == digest, filename
        assert phone.sizes[pid] == os.path.getsize(os.path.join(folder, filename)), filename
    print(f"PASS all {len(REAL_IMAGES)} real images arrived byte-exact at the right partition ids")


def main():
    say = of.say
    of.say = lambda text: None
    test_endpoint_detection()
    test_pit_and_profile()
    test_flash_behaviour()
    if len(sys.argv) > 1:
        of.say = say
        test_real_images(sys.argv[1])
    print("ALL PASSED")


if __name__ == "__main__":
    main()
