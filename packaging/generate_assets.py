#!/usr/bin/env python3
"""FilterLab Pro-Audio Icon Generator.

Generates high-resolution multi-size icons:
- packaging/assets/icon.png (1024x1024)
- packaging/assets/icon.ico (16, 24, 32, 48, 64, 128, 256)
- packaging/assets/icon.icns (Apple ICNS container)
"""

import io
import math
import os
import struct
from PIL import Image, ImageDraw

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)


def generate_icons() -> None:
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = 64
    rect = [pad, pad, size - pad, size - pad]
    radius = 200

    # Base dark console plate
    draw.rounded_rectangle(
        rect, radius=radius, fill=(13, 15, 20, 255), outline=(45, 52, 70, 255), width=10
    )
    draw.rounded_rectangle(
        [pad + 14, pad + 14, size - pad - 14, size - pad - 14],
        radius=radius - 12,
        outline=(0, 210, 255, 70),
        width=4,
    )

    inner_left = pad + 88
    inner_right = size - pad - 88
    inner_top = pad + 120
    inner_bot = size - pad - 120
    zero_y = int(size * 0.56)

    # Logarithmic grid lines
    for y in range(inner_top, inner_bot + 1, 108):
        draw.line([(inner_left, y), (inner_right, y)], fill=(30, 36, 52, 190), width=2)
    for frac in [0.0, 0.18, 0.35, 0.52, 0.68, 0.84, 1.0]:
        gx = int(inner_left + frac * (inner_right - inner_left))
        draw.line([(gx, inner_top), (gx, inner_bot)], fill=(30, 36, 52, 190), width=2)

    # 0 dB reference line
    draw.line([(inner_left, zero_y), (inner_right, zero_y)], fill=(148, 163, 184, 95), width=3)

    # Resonant LowPass Bode curve (0 dB passband, resonant bump at fc, -24 dB/oct roll-off)
    points = []
    width_span = inner_right - inner_left
    fc_norm = 0.54
    q_val = 2.6
    for i in range(0, width_span + 1, 4):
        u = i / width_span
        # Map u in [0, 1] to log ratio w/wc
        log_ratio = (u - fc_norm) * 2.8
        w = math.pow(10.0, log_ratio)
        # 2nd order resonant response squared -> 4th order steeper roll-off visual
        denom_sq = (1.0 - w * w) ** 2 + (w / q_val) ** 2
        mag = 1.0 / math.sqrt(max(denom_sq, 1e-6))
        mag_db = 20.0 * math.log10(max(mag, 1e-4))
        # Clamp display range [-26, +12] dB
        mag_db = max(-26.0, min(12.0, mag_db))
        py = zero_y - (mag_db * 13.5)
        py = max(inner_top + 10, min(inner_bot - 10, py))
        points.append((inner_left + i, py))

    # Fill under curve with translucent cyan
    poly_pts = [(inner_left, inner_bot)] + points + [(inner_right, inner_bot)]
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.polygon(poly_pts, fill=(0, 210, 255, 42))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Subtle secondary peak filter curve (amber)
    peak_pts = []
    for i in range(0, width_span + 1, 6):
        u = i / width_span
        bell = math.exp(-((u - 0.25) ** 2) / 0.008) * 9.0 - math.exp(-((u - 0.78) ** 2) / 0.006) * 8.0
        py = zero_y - bell * 11.0
        peak_pts.append((inner_left + i, py))
    draw.line(peak_pts, fill=(245, 158, 11, 180), width=7)

    # Glow + crisp Bode curve
    draw.line(points, fill=(0, 210, 255, 85), width=24)
    draw.line(points, fill=(0, 224, 255, 255), width=12)
    draw.line(points, fill=(240, 250, 255, 240), width=4)

    # Resonant peak interactive node
    peak_pt = min(points, key=lambda p: p[1])
    nx, ny = int(peak_pt[0]), int(peak_pt[1])
    draw.ellipse([nx - 26, ny - 26, nx + 26, ny + 26], fill=(13, 15, 20, 255), outline=(0, 210, 255, 255), width=8)
    draw.ellipse([nx - 9, ny - 9, nx + 9, ny + 9], fill=(255, 255, 255, 255))

    # Save PNG
    png_path = os.path.join(ASSETS_DIR, "icon.png")
    img.save(png_path, "PNG")

    # Save ICO
    ico_path = os.path.join(ASSETS_DIR, "icon.ico")
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=ico_sizes)

    # Save ICNS
    icns_path = os.path.join(ASSETS_DIR, "icon.icns")
    try:
        img.save(icns_path, format="ICNS")
    except Exception:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        elem_tag = b"ic10"
        elem_len = 8 + len(png_bytes)
        total_len = 8 + elem_len
        with open(icns_path, "wb") as f:
            f.write(b"icns" + struct.pack(">I", total_len))
            f.write(elem_tag + struct.pack(">I", elem_len))
            f.write(png_bytes)

    print(f"Icons saved to {ASSETS_DIR}: icon.png, icon.ico, icon.icns")


if __name__ == "__main__":
    generate_icons()
