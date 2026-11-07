# Add another Samsung model

A phone is described by a folder in `devices/` holding two files:

| File | Contents |
|---|---|
| `device.pit` | The partition table, read from a real phone of that model |
| `device.json` | The model, firmware version, and each image's file, partition and SHA-256, in flash order |

`tools/new_device.py` creates both.

> **Before you start:** if Odin on Windows is available, it's the better-tested choice for other models. See [What's been tested](#whats-been-tested).

## Steps

### 1. Get the right firmware

Use official firmware for the **exact** model and region, with a bootloader version at least as new as the phone's. The [general guide](all-samsung.md#method-4-reinstall-firmware) explains how to choose.

```bash
tools/check_firmware.sh ~/Downloads/MY_FIRMWARE
```

```bash
tools/unpack_firmware.sh ~/Downloads/MY_FIRMWARE firmware/my-phone
```

### 2. Read the phone's partition table

Put the phone in [Download mode](all-samsung.md#enter-download-mode) and run this. It only reads, so it's a safe first test of whether this tool can talk to your phone.

```bash
python3 flasher/odin_flash.py --fresh --dump-pit my-phone.pit
```

Then look at the table:

```bash
python3 tools/pit_info.py my-phone.pit
```

The session stays open after this. Force-restart the phone before flashing it.

### 3. Create the device folder

```bash
python3 tools/new_device.py --model SM-XXXXX --name "Samsung Galaxy XX" --version MY_FIRMWARE_VERSION --firmware ~/Downloads/MY_FIRMWARE --images firmware/my-phone --pit my-phone.pit --out devices/sm-xxxxx
```

### 4. Review the list

The tool prints each image and its partition. **Read this carefully before flashing.**

- Check that it includes the bootloader, boot, recovery, system or `super`, and modem.
- `EFS` should **never** be in the list.
- Read the "Not flashed" line. A `.pit` file there is normal, but a real image means its name didn't match the table, so find out why.

### 5. Flash

Force-restart the phone back into Download mode, then run:

```bash
python3 flasher/odin_flash.py --fresh --device devices/sm-xxxxx --images firmware/my-phone
```

## What's been tested

| What | Status |
|---|---|
| SM-A102N: USB, session, partition table read and flashing all 16 images | Done on a real phone, with the 2026-11-04 version of the flash code |
| Device folders, automatic USB endpoints and the confirmation prompt | Simulator and unit tests only, since these were added after that flash |
| `new_device.py` | Reproduced the SM-A102N's exact image order and hashes from its firmware |
| `--dump-pit` as a separate command | Same read code as the real flash, not run on its own on a phone |
| Any other model | **Not tested** |

## What may differ on other phones

| Difference | What happens |
|---|---|
| Older phones with protocol version below 2 | Refused. They use different transfer sizes |
| USB IDs other than `685d`, `6601` or `68c3` | Not found. Add the ID to `DOWNLOAD_PRODUCTS` |
| Different USB endpoints | Handled automatically |
| Phones using `super.img` | Should work if the table names it, but untested |
| A locked bootloader or Knox policy | The phone refuses unofficial files. Official ones should be accepted |
| Bootloaders that need a different command order | Unknown. The tool stops if a reply doesn't come |

If the phone misbehaves, the stop message and the phone's screen are your best clues. [How it works](how-it-works.md) explains each protocol step, and the small `tools/odin_*.py` scripts help with looking at a stuck phone.

## After it works

Commit `device.json` and `device.pit` for that model. Check `device.pit` first: tables seen so far hold only partition data, but it's worth looking before you publish one. Firmware images must stay out of git, and `.gitignore` already excludes them.
