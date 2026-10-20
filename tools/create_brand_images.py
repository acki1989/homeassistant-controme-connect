"""Erzeugt die Brand-Bilder der Integration (icon.png und logo.png).

Ohne Bildbibliothek: PNG wird direkt geschrieben, die Formen werden mit
4-facher Überabtastung gezeichnet und danach verkleinert (weiche Kanten).

Aufruf:  python3 tools/create_brand_images.py
"""

import math
import os
import struct
import zlib

# Farben der Controme-Oberfläche (Türkis) und Weiß
TURQUOISE = (0x01, 0x9B, 0xB0, 255)
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)

SIZE = 256
SCALE = 4
BIG = SIZE * SCALE


def write_png(path, rows, width, height):
    """Write an RGBA PNG file."""

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    with open(path, "wb") as handle:
        handle.write(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )


def inside_round_rect(x, y, x0, y0, x1, y1, radius):
    """Check if a point is inside a rounded rectangle."""
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + radius), x1 - radius)
    cy = min(max(y, y0 + radius), y1 - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def inside_circle(x, y, cx, cy, radius):
    """Check if a point is inside a circle."""
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def thermometer(x, y):
    """Check if a point belongs to the thermometer shape."""
    # Stem with rounded ends
    if inside_round_rect(x, y, 112 * SCALE, 56 * SCALE, 144 * SCALE, 172 * SCALE, 16 * SCALE):
        return True
    # Bulb
    if inside_circle(x, y, 128 * SCALE, 178 * SCALE, 40 * SCALE):
        return True
    return False


def mercury(x, y):
    """Check if a point belongs to the mercury column."""
    if inside_round_rect(
        x, y, 121 * SCALE, 104 * SCALE, 135 * SCALE, 178 * SCALE, 7 * SCALE
    ):
        return True
    return False


def render(background):
    """Render the image and return the pixel rows."""
    rows = []
    for py in range(SIZE):
        row = bytearray()
        for px in range(SIZE):
            samples = [0, 0, 0, 0]
            for sy in range(SCALE):
                for sx in range(SCALE):
                    x = px * SCALE + sx
                    y = py * SCALE + sy
                    if background is not None and not inside_round_rect(
                        x, y, 0, 0, BIG - 1, BIG - 1, 56 * SCALE
                    ):
                        color = TRANSPARENT
                    elif thermometer(x, y):
                        color = WHITE
                    elif mercury(x, y):
                        color = TURQUOISE
                    elif background is None:
                        color = TRANSPARENT
                    else:
                        color = background
                    samples[0] += color[0]
                    samples[1] += color[1]
                    samples[2] += color[2]
                    samples[3] += color[3]
            count = SCALE * SCALE
            row.extend(
                (
                    samples[0] // count,
                    samples[1] // count,
                    samples[2] // count,
                    samples[3] // count,
                )
            )
        rows.append(row)
    return rows


def main():
    """Create the brand images."""
    target = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "custom_components",
        "controme_connect",
        "brand",
    )
    os.makedirs(target, exist_ok=True)

    icon = os.path.join(target, "icon.png")
    write_png(icon, render(TURQUOISE), SIZE, SIZE)
    print(f"geschrieben: {icon}")

    logo = os.path.join(target, "logo.png")
    write_png(logo, render(None), SIZE, SIZE)
    print(f"geschrieben: {logo}")


if __name__ == "__main__":
    main()
