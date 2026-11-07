# Changelog

## 2026-11-07: public release

- Moved image lists into device folders, so a model is a data file and not code.
- Added automatic USB endpoint detection, as endpoints differ between models.
- Added `--dump-pit` and `tools/new_device.py` for adding other models.
- Added a confirmation that asks you to type the phone's model before erasing it.
- Compare full SHA-256 hashes, not prefixes.
- Refuse bootloaders that use a protocol version older than 2.
- Added guides, diagrams and charts.

These changes passed the simulator and unit tests. They haven't been run on a phone yet, while the flash path itself is unchanged from the version below.

## 2026-11-04: first working flash

- Flashed all 16 images of `A102NKOS3CWD1` to an SM-A102N, after Heimdall 2.0.2 and Thor 1.1.0 failed.
- Send a zero-length packet after each command, which the phone needs once the part size is set.
- Send USB data in 64 KiB chunks after a 1 MiB write failed with `ENOMEM` during `SYSTEM`.
- Added `--from` to continue at a partition without rewriting the bootloader.

[How it works](docs/how-it-works.md#how-the-fix-was-found) has the full story.

## Where this repository's history comes from

The commits from December 2023 are from my earlier `custom_rasp-py_yocto` repository, a Yocto build of a Linux image for the Raspberry Pi, kept unchanged with their original dates. They aren't part of this tool, and their files were removed when this project started. The flasher's own history begins with the first commit dated 2026-11-07.
