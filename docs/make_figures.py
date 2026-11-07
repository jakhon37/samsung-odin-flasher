#!/usr/bin/env python3
"""Draw the data figures in docs/images as light and dark SVGs. Python standard library only.

The partition figures read devices/sm-a102n/device.pit and device.json, so they follow the real table.
"""
import json
import os
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(HERE, "images")
sys.path.insert(0, os.path.join(ROOT, "flasher"))
from odin_flash import BLOCK_BYTES, parse_pit  # noqa: E402

DEVICE = os.path.join(ROOT, "devices", "sm-a102n")
MIB = 1024 * 1024
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"

THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#6f6d68", "grid": "#e1e0d9",
              "axis": "#c3c2b7", "neutral": "#c3c2b7", "s1": "#2a78d6", "s2": "#eb6834", "border": "#e1e0d9"},
    "dark": {"surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#a3a199", "grid": "#2c2c2a",
             "axis": "#383835", "neutral": "#55544f", "s1": "#3987e5", "s2": "#d95926", "border": "#2c2c2a"},
}

# Logged during the two SM-A102N runs: SYSTEM sequences written, seconds since SYSTEM started.
RUN_1MIB = [(0, 0), (20, 19), (40, 38), (60, 71), (80, 119), (100, 176)]
RUN_64KIB = [(0, 0), (20, 20), (40, 40), (60, 61), (80, 81), (100, 102), (114, 116)]

# Blocks of 512 bytes. US values: A10E_USA_SINGLE.pit from the SM-A102U factory package A102USQUAAUD1.
US_BLOCKS = {"SYSTEM": 9420800, "VENDOR": 1015808, "PRODUCT": 1032192, "CACHE": 1228800}


def text(x, y, content, fill, size=13, anchor="start", weight=400):
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{escape(content)}</text>')


def rect(x, y, w, h, fill, radius=0):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{h:.1f}" fill="{fill}" rx="{radius}"/>'


def line(x1, y1, x2, y2, stroke, width=1):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"/>'


def legend_item(x, y, colour, label, theme):
    return rect(x, y - 10, 12, 12, colour, 3) + text(x + 18, y, label, theme["ink2"])


def page(width, height, title, subtitle, body, theme):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'font-family="{FONT}" role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>'
            + f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{theme["surface"]}" '
              f'stroke="{theme["border"]}"/>'
            + text(24, 34, title, theme["ink"], 17, weight=600) + text(24, 56, subtitle, theme["ink2"], 13)
            + body + "</svg>\n")


def size_label(mib):
    if mib >= 1024:
        return f"{mib / 1024:.2f} GiB"
    if mib >= 1:
        return f"{mib:.1f} MiB".replace(".0 MiB", " MiB")
    return f"{mib * 1024:.1f} KiB"


def storage_map(theme):
    """The phone's main storage to scale, in table order, up to where USERDATA begins."""
    with open(os.path.join(DEVICE, "device.pit"), "rb") as f:
        entries = parse_pit(f.read())
    with open(os.path.join(DEVICE, "device.json")) as f:
        flashed = {image["partition"] for image in json.load(f)["images"]}
    width, left, strip_w, top, height = 900, 24, 852, 118, 44
    main = [e for e in entries if e["offset"] >= 8192 and e["blocks"]]
    start = main[0]["offset"]
    end = entries[-1]["offset"]
    userdata_w = 100
    scale = (strip_w - userdata_w) / (end - start)
    body = ""
    for entry in main:
        x = left + (entry["offset"] - start) * scale
        w = entry["blocks"] * scale
        colour = theme["s1"] if entry["partition"] in flashed else theme["neutral"]
        body += rect(x, top, max(w - 1.5, 0.6), height, colour)
    x_user = left + strip_w - userdata_w
    body += rect(x_user, top, userdata_w, height, theme["s1"], 4)
    body += text(x_user + userdata_w / 2, top + height / 2 + 4, "USERDATA", "#ffffff", 12, "middle", 600)
    body += text(x_user + userdata_w / 2, top + height + 20, "rest of storage", theme["ink2"], 12, "middle")
    body += text(x_user + userdata_w / 2, top + height + 36, "(not to scale)", theme["muted"], 12, "middle")

    def bracket(names, label, detail, y=top - 8, anchor="middle"):
        group = [e for e in main if e["partition"] in names]
        x1 = left + (group[0]["offset"] - start) * scale
        x2 = left + (group[-1]["offset"] + group[-1]["blocks"] - start) * scale
        at = x1 if anchor == "start" else (x1 + x2) / 2
        return (line(x1, y, x2, y, theme["axis"]) + text(at, y - 22, label, theme["ink"], 13, anchor, 600)
                + text(at, y - 7, detail, theme["ink2"], 12, anchor))

    def mib_of(names):
        return sum(e["blocks"] for e in main if e["partition"] in names) * BLOCK_BYTES / MIB

    low = [e["partition"] for e in main if e["offset"] < 557056]
    body += bracket(low, "Boot, radio, EFS", f"{mib_of(low):.0f} MiB", anchor="start")
    body += bracket(["SYSTEM"], "SYSTEM", f"{mib_of(['SYSTEM']):,.0f} MiB")
    body += bracket(["VENDOR"], "VENDOR", f"{mib_of(['VENDOR']):.0f} MiB")
    body += bracket(["CACHE"], "CACHE", f"{mib_of(['CACHE']):.0f} MiB", top - 8)
    tail = ["CARRIER", "OMR", "CP_DEBUG", "NAD_FW"]
    x_product = left + (next(e for e in main if e["partition"] == "PRODUCT")["offset"] - start) * scale
    body += text(x_product, top + height + 20, f"PRODUCT {mib_of(['PRODUCT']):.0f} MiB", theme["ink2"], 12, "end")
    x_tail = left + (next(e for e in main if e["partition"] == "CARRIER")["offset"] - start) * scale
    body += text(x_tail, top + height + 36, f"CARRIER, OMR, CP_DEBUG, NAD_FW {mib_of(tail):.0f} MiB", theme["ink2"], 12, "end")
    legend_y = top + height + 72
    body += legend_item(left, legend_y, theme["s1"], "Written by a full flash", theme)
    body += legend_item(left + 200, legend_y, theme["neutral"], "Left alone", theme)
    return page(width, legend_y + 24, "SM-A102N main storage, to scale",
                f"From the partition table read off the phone. {len(main) + 1} of its {len(entries)} partitions are in this strip.", body, theme)


def image_sizes(theme):
    with open(os.path.join(DEVICE, "device.json")) as f:
        images = json.load(f)["images"]
    sizes = {
        "sboot.bin": 4194304, "param.bin": 1904640, "cm.bin": 8388608, "vbmeta.img": 9104, "boot.img": 37748736,
        "recovery.img": 55574528, "dt.img": 8388608, "dtbo.img": 8388608, "system.img": 3577959244,
        "vendor.img": 163328232, "userdata.img": 930869756, "modem.bin": 37413808, "modem_debug.bin": 5242880,
        "cache.img": 78020, "omr.img": 53360, "product.img": 19058824,
    }
    width, label_w, right, top, row = 900, 130, 110, 80, 24
    plot = width - 24 - label_w - right
    largest = max(sizes.values())
    body = ""
    x0 = 24 + label_w
    for i, image in enumerate(images):
        y = top + i * row
        size = sizes[image["file"]]
        w = max(size / largest * plot, 2)
        body += text(x0 - 10, y + 13, image["partition"], theme["ink2"], 13, "end")
        body += rect(x0, y + 2, w, row - 8, theme["s1"], 4)
        body += text(x0 + w + 8, y + 13, size_label(size / MIB), theme["ink"], 13)
    bottom = top + len(images) * row
    body = line(x0, top - 4, x0, bottom - 2, theme["axis"]) + body
    return page(width, bottom + 12, "SYSTEM is most of what gets written",
                "The 16 images of A102NKOS3CWD1, unpacked, in flash order: 4.5 GiB in total.", body, theme)


def system_timing(theme):
    width, height, left, right, top, bottom = 900, 424, 70, 190, 120, 62
    plot_w, plot_h = width - left - right, height - top - bottom
    x_max, y_max = 120, 200

    def px(x):
        return left + x / x_max * plot_w

    def py(y):
        return top + plot_h - y / y_max * plot_h

    body = ""
    for tick in range(0, y_max + 1, 50):
        body += line(left, py(tick), left + plot_w, py(tick), theme["grid"] if tick else theme["axis"])
        body += text(left - 10, py(tick) + 4, f"{tick}", theme["muted"], 12, "end")
    for tick in range(0, x_max + 1, 20):
        body += text(px(tick), top + plot_h + 20, f"{tick}", theme["muted"], 12, "middle")
    body += text(left + plot_w / 2, top + plot_h + 44, "SYSTEM sequences written (30 MiB each)", theme["ink2"], 13, "middle")
    body += text(24, top - 12, "Seconds", theme["ink2"], 13)
    for points, colour, label, detail in (
        (RUN_1MIB, theme["s2"], "First run", "1 MiB USB writes"),
        (RUN_64KIB, theme["s1"], "Second run", "64 KiB USB writes"),
    ):
        path = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in points)
        body += f'<polyline points="{path}" fill="none" stroke="{colour}" stroke-width="2" stroke-linejoin="round"/>'
        for x, y in points:
            body += (f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="4.5" fill="{colour}" '
                     f'stroke="{theme["surface"]}" stroke-width="2"/>')
        x, y = points[-1]
        body += text(px(x) + 12, py(y) + 0, label, theme["ink"], 13, weight=600)
        body += text(px(x) + 12, py(y) + 16, detail, theme["ink2"], 12)
    body += legend_item(left, 80, theme["s2"], "First run: last logged point, stopped soon after", theme)
    body += legend_item(left + 350, 80, theme["s1"], "Second run: finished", theme)
    return page(width, height, "SYSTEM write time, two real runs on one phone",
                "Two runs only, and the phone was restarted between them, so this doesn't prove the cause.", body, theme)


def region_partitions(theme):
    with open(os.path.join(DEVICE, "device.pit"), "rb") as f:
        korean = {e["partition"]: e["blocks"] for e in parse_pit(f.read())}
    width, label_w, right, top, group = 900, 100, 110, 104, 62
    plot = width - 24 - label_w - right
    largest = max(US_BLOCKS.values())
    x0 = 24 + label_w
    body = legend_item(24, 80, theme["s1"], "Korean SM-A102N", theme) + legend_item(190, 80, theme["s2"], "US SM-A102U", theme)
    for i, (name, us_blocks) in enumerate(US_BLOCKS.items()):
        y = top + i * group
        body += text(x0 - 10, y + 27, name, theme["ink2"], 13, "end")
        for j, (blocks, colour) in enumerate(((korean[name], theme["s1"]), (us_blocks, theme["s2"]))):
            bar_y = y + j * 24
            w = blocks / largest * plot
            body += rect(x0, bar_y, w, 20, colour, 4)
            body += text(x0 + w + 8, bar_y + 15, size_label(blocks * BLOCK_BYTES / MIB), theme["ink"], 13)
    bottom = top + len(US_BLOCKS) * group
    body += line(x0, top - 4, x0, bottom - 12, theme["axis"])
    return page(width, bottom, "Same phone name, different partition layout",
                "This phone's table against the US factory package's table. A normal US release may differ.", body, theme)


FIGURES = {
    "storage-map": storage_map,
    "image-sizes": image_sizes,
    "system-timing": system_timing,
    "region-partitions": region_partitions,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, figure in FIGURES.items():
        for mode, theme in THEMES.items():
            path = os.path.join(OUT, f"{name}-{mode}.svg")
            with open(path, "w") as f:
                f.write(figure(theme))
            print(path)


if __name__ == "__main__":
    main()
