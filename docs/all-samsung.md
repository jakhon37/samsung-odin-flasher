# Resetting and reinstalling firmware on Samsung Galaxy phones

A general guide for Samsung Galaxy phones you own or have permission to work on. For the SM-A102N, see [its own guide](sm-a102n.md). To use this repository's flasher on another model, see [Add another model](new-model.md).

**Start with the simplest method that fits.** Many phones only need a factory reset, not a firmware flash.

| Your situation | What to do | Erases data? |
|---|---|---|
| Phone works and you want it clean | [Method 1: reset from Settings](#method-1-reset-from-settings) | Yes |
| Phone is lost, or you can't reach it | [Method 2: reset remotely](#method-2-reset-remotely) | Yes |
| Won't start Android, or forgot your screen lock | [Method 3: reset from Recovery](#method-3-reset-from-recovery) | Yes |
| Boot loop, "firmware update error", or recovery can't fix it | [Method 4: reinstall firmware](#method-4-reinstall-firmware) | Usually |
| Download mode is gone, a flash keeps failing, or you're locked out by an account | [Samsung service centre](#when-to-go-to-a-service-centre) | Depends |

> **Warnings**
> - **Back up first** if you still can. A reset can't be undone.
> - **Remember the accounts on the phone.** After some resets, it asks for the previous Google account. See [Account lock](#account-lock-after-a-reset-frp).
> - **Don't buy or run "FRP bypass" tools.** They're often unsafe, and removing the lock on a phone that isn't yours may be illegal. The right fixes are below.

---

## Find out which phone you have

You need the **exact model number**. "Galaxy A10e" isn't enough: the SM-A102N and SM-A102U are both sold as A10e and need different firmware.

| Where | How |
|---|---|
| Settings | **Settings > About phone** |
| Dialler | Type `*#1234#` to see the model's firmware version (may not work on all phones) |
| Download mode screen | Often shows the model on the top lines |
| Back label or box | Look for `SM-` followed by letters and numbers |
| PC, with USB debugging on | `adb shell getprop ro.product.model` |

The letters at the end of the model usually show the market, such as `N` for Korea and `U` for the US. It's a model difference, not only a language difference.

---

## Method 1: reset from Settings

This is the safest way, and the one Samsung recommends. Samsung says the account lock is triggered by resets done **any other way**.

1. Back up what you want to keep.
2. Remove your accounts, if you're giving the phone away: **Settings > Accounts and backup > Manage accounts**. Menu names vary by Android version.
3. Go to **Settings > General management > Reset > Factory data reset**.
4. Tap **Reset**, then **Delete all**.
5. Enter your Samsung account password if asked.

---

## Method 2: reset remotely

If the phone is lost but online, sign in with the account that's already on it. You need that account's password.

- **Samsung Find:** <https://smartthingsfind.samsung.com>
- **Google Find Hub:** <https://www.google.com/android/find>

Choose the erase option. These sites may change, and they only work if the phone is on and connected.

---

## Method 3: reset from Recovery

Use this if Android won't start or you've forgotten the screen lock.

> **After this kind of reset, the phone will probably ask for its previous Google account.** Make sure you know it before you start. See [Account lock](#account-lock-after-a-reset-frp).

### Enter Recovery

Combos differ by model, so try the one that matches your phone's buttons.

1. Turn the phone off fully. If it's stuck, force-restart it: hold **Volume Down + Power** for about 10 seconds.
2. Hold the keys below until the Samsung logo shows, then release **Power** and keep the others held until the recovery menu shows.

| Phone's buttons | Common combo for Recovery |
|---|---|
| No Home or Bixby button (most newer phones) | **Volume Up + Power** |
| Bixby button (roughly S8 to S10, Note 8 to 10) | **Volume Up + Bixby + Power** |
| Physical Home button (older phones) | **Volume Up + Home + Power** |

**If it doesn't work:**
- Try again with the phone connected to a computer by USB. Some newer models need this.
- Some guides list **Volume Up + Volume Down + Power** for newer models.
- Search for your exact model number and "recovery mode".
- If Android still works and USB debugging is on, run the command below.

```bash
adb reboot recovery
```

### Wipe the phone

**Volume** keys move the highlight and **Power** selects.

1. Select **Wipe data/factory reset**.
2. Select **Factory data reset** (or **Yes**).
3. Wait for "Data wipe complete".
4. Select **Reboot system now**.

The first boot can take 5 minutes or more.

---

## Method 4: reinstall firmware

This reinstalls the phone's whole operating system. It can fix a phone that a reset can't, but it's also the riskiest method.

### Rules that keep you safe

1. **Use firmware for the exact model.** Never flash firmware for another model, even one with the same marketing name.
2. **Don't go to an older bootloader version.** See [Read the firmware name](#read-the-firmware-name).
3. **Flash official Samsung firmware only** if you want to keep Knox and warranty status. Custom software can permanently trip Knox.
4. **Don't use `COMBINATION` or `FAC` packages.** They're factory test builds, not normal firmware.
5. **Leave these off** unless you know exactly why you need them: **Re-Partition**, **Nand Erase**, a separate **PIT** file, and `EFS` clearing. They can wipe the phone's IMEI and network identity.
6. **Charge the phone first**, ideally to 50% or more. Use a good data cable plugged directly into the PC, with no hub.
7. **Don't unplug during writing.**

### Get the firmware

| Source | Notes |
|---|---|
| **Smart Switch** (Windows or Mac) | Official. Can reinstall firmware itself, with no download needed. |
| [Bifrost](https://github.com/zacharee/Bifrost) | Open-source tool that downloads firmware from Samsung's servers |
| [samloader](https://github.com/martinetd/samloader) | Open-source command-line downloader. Updated less often. |
| [SamFW](https://samfw.com/) | Unofficial website. The SM-A102N firmware in this repository's guides came from here. Use it for firmware downloads only, not its other tools. |
| Other firmware websites | Common, but not official. Avoid sites that push extra tools. |

**Check any download from a website:** run `tools/check_firmware.sh` on it. This catches a damaged file, but the checksum comes inside the same file, so it can't prove the file came from Samsung. The phone's own signature check is the stronger protection.

**Choosing a region (CSC):** use the same one as your phone, such as `KOO` in Korea. Changing region is possible on some phones, but it isn't needed for a repair.

### Read the firmware name

Firmware names follow a pattern. Using `A102NKOS3CWD1` as an example:

| Part | Example | Meaning |
|---|---|---|
| Model | `A102N` | **Must match your phone** |
| Region and type | `KO` | Market or region group |
| Update type | `S` | Commonly `S` for security, `U` for upgrade |
| **Bootloader version** | **`3`** | **Must be the same as or higher than your phone's** |
| Major release | `C` | Moves up with bigger releases |
| Year | `W` | `W` is 2023 |
| Month | `D` | `A` is January, so `D` is April |
| Build | `1` | Build number within that month |

This pattern is common community knowledge, not an official Samsung specification. In the newest firmware the bootloader digit can be a letter, which comes after 9.

**Tip:** the newest firmware for your exact model and region is usually the safest choice, because it can't be an older bootloader version.

### Check the files

A full firmware unzips into these files:

| File | Contains | Notes |
|---|---|---|
| `BL_*.tar.md5` | Bootloader | Can be missing on some older firmware |
| `AP_*.tar.md5` | Android system, the biggest file | Always needed |
| `CP_*.tar.md5` | Radio firmware | Wi-Fi-only tablets may not have one |
| `CSC_*.tar.md5` | Region settings and partition table | **Clean install, erases data** |
| `HOME_CSC_*.tar.md5` | Region settings | **Tries to keep data.** Use one CSC, never both. |

`HOME_CSC` isn't guaranteed to keep your data, and it generally needs the same region as your current firmware. A phone that's already failing often needs the full `CSC`.

To check every file's built-in checksum on Linux, run this in the firmware folder. Every line should say `OK`.

```bash
for f in *.tar.md5; do
  line=$(tail -c 200 "$f" | tail -n1)
  want=$(echo "$line" | cut -d' ' -f1)
  have=$(head -c -"$(echo "$line" | wc -c)" "$f" | md5sum | cut -d' ' -f1)
  [ "$want" = "$have" ] && echo "OK   $f" || echo "BAD  $f"
done
```

### Enter Download mode

Combos differ by model. The screen is usually blue or teal and may say "Downloading", or show a warning first where you press **Volume Up** to continue.

| Phone's buttons | Common combo for Download mode |
|---|---|
| No Home or Bixby button | With the phone off, hold **Volume Up + Volume Down** and plug in a USB cable from the PC |
| Bixby button | With the phone off, hold **Volume Down + Bixby + Power** |
| Physical Home button | With the phone off, hold **Volume Down + Home + Power**, then press **Volume Up** |

These combos are general knowledge, so search for your exact model if one doesn't work. If Android works and USB debugging is on:

```bash
adb reboot download
```

On Linux, check that the PC can see the phone. Download mode is usually `04e8:685d`, and the name may say "GT-I9100", which is normal.

```bash
lsusb -d 04e8:
```

**To leave Download mode:** hold **Volume Down + Power** for about 10 seconds.

---

## Choose a flashing tool

| Tool | System | Best for | Limits |
|---|---|---|---|
| **Smart Switch** | Windows, Mac | The easiest official option | May not offer every phone or situation |
| **Odin** | Windows | The standard method, and the most reliable | Not an official public release, so choose your source with care |
| **Heimdall** | Linux, Mac, Windows | Older phones | The Ubuntu version (2.0.2) failed on a 2019 phone |
| **Thor** | Linux | Some phones Heimdall can't handle | Archived, with known bugs |
| **`odin_flash.py`** (this repository) | Linux | The SM-A102N, and models you [add yourself](new-model.md) | Other models are untested |

**If you can borrow a Windows PC, use Odin.** It's the method with the most help available for other models.

### Odin (Windows)

1. Install the Samsung USB driver, and close Smart Switch and Kies.
2. Run Odin as administrator.
3. Put the phone in Download mode and connect it. An `ID:COM` box should light up.
4. Load the files. Loading the big `AP` file can take a few minutes.
   - `BL_...` in **BL**
   - `AP_...` in **AP**
   - `CP_...` in **CP**
   - `CSC_...` or `HOME_CSC_...` in **CSC**
5. In **Options**, keep only **Auto Reboot** and **F. Reset Time** on. Leave **Re-Partition** off.
6. Leave the **Pit** tab empty.
7. Press **Start**. Wait for **PASS!** in green, or **FAIL!** in red.

### Heimdall (Linux)

Heimdall flashes unpacked images, one per partition.

1. Install the tools and check the connection:

   ```bash
   sudo apt install heimdall-flash lz4
   heimdall detect
   ```

2. Unpack the firmware. Leave out `HOME_CSC` for a clean install.

   ```bash
   mkdir -p img
   for f in BL_*.tar.md5 AP_*.tar.md5 CP_*.tar.md5 CSC_*.tar.md5; do
     tar -xf "$f" --exclude='meta-data*' -C img
   done
   cd img
   lz4 -dm --rm *.lz4
   ```

3. Print the phone's partition table. Each entry gives a **Partition Name** and a **Flash Filename**, and that's your map from file to partition.

   ```bash
   heimdall print-pit --no-reboot
   ```

4. Flash using that map. Use your phone's names, because they differ between models. This is an example only:

   ```bash
   heimdall flash --resume --BOOTLOADER sboot.bin --BOOT boot.img --RECOVERY recovery.img --SYSTEM system.img
   ```

   Include every image from your firmware that has a matching entry. `--resume` continues the session left open by step 3.

### Thor (Linux)

Thor runs commands in its own shell. It's [archived](https://github.com/Samsung-Loki/Thor), so problems won't be fixed.

```text
connect
begin odin
flashTar /path/without/spaces
```

**Known problems:**
- **Paths with spaces** don't work.
- **Partition table read:** on some phones, it times out straight after `begin odin`.
- **`flashTar` with `.lz4` firmware:** version 1.1.0 can show an empty menu. A possible workaround is to make a plain tar holding the unpacked images, with their names exactly as listed in the partition table. This wasn't proven: on the phone we tried, Thor timed out before reaching the menu.

---

## When a flash fails

### Rules that save time

1. **After a failed attempt, force-restart the phone before trying again.** A stuck session can survive a USB reset or replug. On the phone we tested, even a new connection got no reply until it restarted.
2. **Change one thing at a time:** first the USB port, then the cable, and then the tool.
3. **Read the phone's screen.** It often shows the real reason in small text, while the PC only says `FAIL`.
4. **A frozen progress bar may mean the PC has stopped.** Check whether the tool is still running before you assume the phone is the problem.
5. **Don't panic at "firmware update error".** If the phone still connects in Download mode, it can usually be reflashed.

### Errors on the phone or in the tool

These come from general reports and can vary by model.

| Message | Usual cause | What to do |
|---|---|---|
| `SW REV CHECK FAIL` or `DEVICE ... BINARY` | Firmware is older than the phone's | Use firmware with the same or a higher bootloader version. You can't get around this. |
| `SECURE CHECK FAIL` or `Auth` | Wrong or unsigned file for this phone | Check the exact model and get official firmware |
| `Re-partition operation failed` or `PIT` errors | Wrong model, or a wrong PIT file | Check the model. Leave **Re-Partition** off. |
| `Only official released binaries` | Custom file on a locked phone | Use official firmware |
| Blocked by FRP or KG | An account or device lock is active | Sign in to the phone, or go to a service centre |
| Odin stops at `SetupConnection` | Cable, port or driver | Change the port or cable, reinstall the driver |
| Heimdall: `Failed to receive handshake response` | A stuck session | Force-restart the phone |
| Heimdall: stops at `Beginning session` | The tool can't handle this phone | Try another tool |
| Thor: `Failed to bulk read: Connection timed out` | Often a known Thor bug | Try Odin, or see [How it works](how-it-works.md#the-empty-packet) |
| No Samsung device in `lsusb -d 04e8:` | Not in Download mode, or a charge-only cable | Check the phone's screen, use a data cable |

### After the flash

The first boot can take 5 to 10 minutes.

| You see | What to do |
|---|---|
| Welcome screen | Done |
| Recovery with "Installing update" | Wait |
| Recovery menu, or a boot loop for over 10 minutes | [Wipe from Recovery](#wipe-the-phone), which is often needed after a flash |
| "firmware update error" | Force-restart, reach Download mode, flash again |
| No mobile signal or IMEI missing | Stop and go to a service centre. The phone's identity may be damaged. |

---

## Account lock after a reset (FRP)

If a Google account was on the phone, it may ask for that account after a reset. Samsung calls this Factory Reset Protection. A firmware flash doesn't remove it.

**What works:**
1. Sign in with the Google account that was on the phone.
2. On Android 9 or later, you may be able to use the old screen lock instead.
3. Forgot the password? Use [Google's account recovery](https://accounts.google.com/signin/recovery).
4. Go to a service centre with your proof of purchase.

**To avoid it when selling or giving away a phone:** remove the accounts, then reset from Settings ([Method 1](#method-1-reset-from-settings)).

**Bought a used phone that's locked?** Ask the seller to remove it from their account. If they can't, the phone may be stolen.

---

## When to go to a service centre

- The phone won't reach Download mode at all.
- A flash failed on the bootloader, and the phone shows nothing.
- You see the same storage error after two tries, such as `Write` or `Erase`.
- The IMEI is missing or mobile signal is gone after a flash.
- You're locked out, and can't recover the account.

---

## Sources

- [Samsung: perform a factory reset](https://www.samsung.com/au/support/mobile-devices/perform-a-factory-reset-on-samsung-galaxy-device/)
- [Samsung Community: Factory Reset Protection](https://eu.community.samsung.com/t5/tablets/samsung-tablet/m-p/6943826)
- [Wccftech: recovery mode on Galaxy phones](https://wccftech.com/how-to/how-to-enter-recovery-mode-in-galaxy-phones/)
- [Samsung Community: CSC or HOME_CSC](https://r2.community.samsung.com/t5/Others/CSC-or-Home-csc/m-p/6912859/highlight/true)
- [Thor issues](https://github.com/Samsung-Loki/Thor/issues), [Heimdall](https://github.com/Benjamin-Dobell/Heimdall)

Button combos, menu names and error messages change between models and Android versions. If a step here doesn't match your phone, check the steps for your exact model number.
