# Flash the Galaxy A10e (SM-A102N)

This reinstalls Samsung's stock Korean firmware from a Linux PC.

| | |
|---|---|
| Phone | Samsung Galaxy A10e, model **SM-A102N** |
| Firmware | **A102NKOS3CWD1** (Android 11, region KOO) |
| Time | About 3 minutes of writing, then up to 10 minutes for the first boot |

> **A full flash erases everything on the phone.** Back up what you can.
>
> **Use this only on an SM-A102N.** Check the model on the back label or in **Settings > About phone**.

All commands run from the repository's main folder.

---

## Step 1: Install what you need

```bash
sudo apt install python3 lz4 usbutils heimdall-flash
```

Heimdall itself isn't used. Its package adds the USB rule that lets you flash without `sudo`.

---

## Step 2: Prepare the firmware

Download firmware `A102NKOS3CWD1` for the SM-A102N (see [where to get firmware](all-samsung.md#get-the-firmware)), and unzip it. You should have these files:

| File | Contains |
|---|---|
| `BL_*.tar.md5` | Bootloader |
| `AP_*.tar.md5` | Android system |
| `CP_*.tar.md5` | Radio firmware |
| `CSC_OMC_*.tar.md5` | Region settings, clean install |
| `HOME_CSC_OMC_*.tar.md5` | Not used by this tool |

Check them. Every line should say `OK`, and this takes a minute or two.

```bash
tools/check_firmware.sh ~/Downloads/A102NKOS3CWD1
```

Unpack them into plain images. `firmware/` is ignored by git, so the images won't be committed.

```bash
tools/unpack_firmware.sh ~/Downloads/A102NKOS3CWD1 firmware/img
```

---

## Step 3: Enter Download mode

Try these in order, with the cable plugged directly into the PC:

- **From the "firmware update error" screen:** this already counts as Download mode on this phone. Hold **Volume Down + Power** for about 10 seconds to force-restart it, and let it come back to the same screen.
- **With the phone off:**
  1. Hold **Volume Down + Power** until the screen goes off.
  2. Straight away, hold **Volume Up + Volume Down** and plug in the cable.
  3. If a blue warning screen appears, press **Volume Up** to continue.
- **From Android, with USB debugging on:**

  ```bash
  adb reboot download
  ```

The first method worked on the test phone. The other two are the usual ones for Samsung phones of this age, but weren't tried on it.

Then check the connection. The output must include `04e8:685d`. It may say "GT-I9100", which is normal.

```bash
lsusb -d 04e8:
```

**Before flashing:** if any flasher has opened a session since the phone last restarted, force-restart it first. Replugging the cable isn't enough.

---

## Step 4: Flash

```bash
python3 flasher/odin_flash.py --fresh --device devices/sm-a102n --images firmware/img 2>&1 | tee flash.log
```

Type `SM-A102N` when it asks. **Don't touch the phone or cable until the last line says `DONE`.**

### Hands-free option

Start this first, then force-restart the phone. It waits for Download mode and then flashes without asking, because `--yes` skips the confirmation.

```bash
until lsusb -d 04e8:685d >/dev/null; do sleep 1; done; sleep 10; python3 flasher/odin_flash.py --fresh --device devices/sm-a102n --images firmware/img --yes 2>&1 | tee flash.log
```

### What you should see

| Line | Meaning |
|---|---|
| `session begun, bootloader version 0x00030000` | The phone answered |
| `partition table matches; 16 images mapped` | The phone's layout is the expected one |
| `all 16 image hashes match the factory firmware` | The files are good. This takes about 25 seconds |
| `total ... bytes accepted; writing starts now` | **Writing begins. Don't touch anything from now on** |
| `SYSTEM: 20/114 sequences` | Progress on the biggest image, which can slow down |
| `all images flashed`, `reboot requested`, `DONE` | Finished. The phone restarts by itself |

**If the phone's progress bar stops,** look at the PC. If the tool has exited, the bar won't move again, so follow the stop message. If it's still printing lines, wait.

---

## Step 5: First boot

1. Leave the phone alone. The Samsung logo can stay up for 5 minutes or more, and the phone may restart once.
2. Success is the welcome screen asking for your language.
3. If it asks for a Google account, use the one that was on the phone before. This is Samsung's normal anti-theft check.

### If it opens Android Recovery

- **A robot, "Installing system update" or "Erasing":** it's working. Wait up to 5 minutes.
- **A text menu starting with "Reboot system now":** do a factory reset. **Volume** keys move the highlight, and **Power** selects.
  1. Select **Wipe data/factory reset**.
  2. Select **Factory data reset** (or **Yes**).
  3. Wait for "Data wipe complete".
  4. Select **Reboot system now**.

If it comes back to recovery, read the yellow or red text at the bottom of the screen. It says what failed.

---

## Options

| Option | When to use it |
|---|---|
| `--fresh` | Normal start, on a freshly restarted phone |
| `--from PARTITION` | A flash stopped part-way. Skips the images before this partition |
| `--resume` | Use a session that's already open. See below |
| `--dump-pit FILE` | Save the phone's partition table and write nothing else |
| `--yes` | Skip the confirmation |

### Continue after a stopped flash

The stop message says where it stopped, such as `at SYSTEM sequence 101 part 4`. Force-restart the phone, then continue from that partition. It's written again from its start, so nothing is left half done, and earlier images such as the bootloader aren't written twice.

```bash
python3 flasher/odin_flash.py --fresh --device devices/sm-a102n --images firmware/img --from SYSTEM
```

Partition names, in flash order:

`BOOTLOADER` `PARAM` `CM` `VBMETA` `BOOT` `RECOVERY` `DTB` `DTBO` `SYSTEM` `VENDOR` `USERDATA` `RADIO` `CP_DEBUG` `CACHE` `OMR` `PRODUCT`

Only skip images the log shows as `done`. If you're unsure, run the full flash.

### `--resume`

This skips the handshake and uses an open session. It only works if no image was being sent when that session stopped. If you're unsure, force-restart and use `--fresh`.

### What the tool doesn't do

- **Keep your data.** The flash list includes `USERDATA`. To try keeping data, use Odin on Windows with `HOME_CSC`.
- **Flash just one partition.** `--from` always continues to the end of the list.

---

## If something goes wrong

The last line says whether the phone was written to:

| Last line | Exit code | Meaning |
|---|---|---|
| `DONE` | 0 | Finished |
| `STOPPED BEFORE ANY WRITE` | 2 | Phone unchanged. Fix the cause and try again |
| `STOPPED AFTER WRITING BEGAN` | 3 | Part-flashed. It won't boot until a flash finishes |

If a session was opened, force-restart the phone before trying again.

| Message | Likely cause | What to do |
|---|---|---|
| `expected one phone in Download mode` | Wrong mode, or another Samsung device is plugged in | Go back to Step 3, and unplug other Samsung devices |
| `phone not found on USB, or no permission` | No USB permission | Install `heimdall-flash` and replug, or run with `sudo` |
| `heimdall is running` | Another flasher is open | Close it, then force-restart the phone |
| `handshake: no reply (ETIMEDOUT)` | An old session is stuck on the phone | Force-restart, then use `--fresh`. Replugging won't fix it |
| `PIT request: no reply` with `--resume` | The session has gone stale | Force-restart, then use `--fresh` |
| `partition table differs from the verified copy` | The layout changed, or this is a different phone | **Stop.** Don't force it. Find out why first |
| `hash differs from the factory image` | An image is damaged or wrong | Redo Step 2 |
| `phone refused, code -5 (Auth)` | Signature rejected, often wrong or older firmware | Read the phone's screen. Don't retry until you know why |
| `phone refused` with `-4`, `-3` or `-2` | The phone couldn't write to its storage | Force-restart and try once more. If it repeats, see a service centre |
| `no ack` or `no reply` while writing | USB connection problem | Try another port or cable, force-restart, then use `--from` |
| `USB write ... ENOMEM` | The PC is short of free memory | Close heavy programs, force-restart, then use `--from` |

**If the buttons do nothing,** charge the phone on a wall charger for 30 minutes and try again.

**If Download mode is gone, or a flash keeps failing,** a [Samsung service centre](all-samsung.md#when-to-go-to-a-service-centre) is the safe next step.
