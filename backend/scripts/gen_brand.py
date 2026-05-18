"""Render the Hermesx402 brand sheet to a PNG (exact fonts + colours)."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

import os

_BF = os.path.join(os.path.dirname(__file__), "..", "_bf")
SG = os.path.join(_BF, "sg.ttf")    # Space Grotesk (variable)
PM = os.path.join(_BF, "pm.ttf")    # IBM Plex Mono Regular
PMB = os.path.join(_BF, "pmb.ttf")  # IBM Plex Mono Bold

PAPER = "#F4EFE2"
INK = "#1A1712"
ACCENT = "#1F2EE6"


def sg(size: int, weight: int = 700):
    f = ImageFont.truetype(SG, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def mono(size: int, bold: bool = False):
    return ImageFont.truetype(PMB if bold else PM, size)


W, H = 1480, 1780
img = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(img)

# outer ledger frame
d.rectangle([24, 24, W - 24, H - 24], outline=INK, width=2)

# masthead strip
d.line([24, 96, W - 24, 96], fill=INK, width=2)
d.text((48, 50), "NO. 402 · BRAND LEDGER", font=mono(20), fill="#6B6353")
d.text((W - 230, 50), "EST. 2026", font=mono(20), fill="#6B6353")

# wordmark
d.text((48, 140), "HERMES", font=sg(110, 700), fill=INK)
wm = d.textlength("HERMES", font=sg(110, 700))
d.text((48 + wm + 6, 140), "x402", font=sg(110, 700), fill=ACCENT)
d.text((52, 280),
       "Autonomous AI agents that pay for data — on-chain, on the record.",
       font=mono(22), fill="#3A352C")

# ── Typography ──
y = 360
d.text((48, y), "§ TYPOGRAPHY", font=mono(20, True), fill="#6B6353")
d.line([48, y + 34, W - 48, y + 34], fill="#9A9081", width=1)
y += 60
d.text((48, y), "Space Grotesk", font=sg(46, 700), fill=INK)
d.text((640, y + 6), "Display · headings · logo  (700 / 600 / 500)",
       font=mono(20), fill="#6B6353")
y += 70
d.text((48, y), "ABCDEFG abcdefg 0123456789  $0.12  x402",
       font=sg(40, 600), fill=INK)
y += 86
d.text((48, y), "IBM Plex Mono", font=mono(46, True), fill=INK)
d.text((640, y + 6), "Data · numbers · ledger  (400 / 500 / 600)",
       font=mono(20), fill="#6B6353")
y += 70
d.text((48, y), "ABCDEFG abcdefg 0123456789  −0.02  SETTLED",
       font=mono(38), fill=INK)

# ── Colours ──
y += 110
d.text((48, y), "§ COLOUR", font=mono(20, True), fill="#6B6353")
d.line([48, y + 34, W - 48, y + 34], fill="#9A9081", width=1)
y += 64

SW = [
    ("Accent", "#1F2EE6", "cobalt · links · the x402"),
    ("Accent ink", "#0E1696", "accent hover / pressed"),
    ("Ink", "#1A1712", "text · borders · marks"),
    ("Ink 700", "#3A352C", "secondary text"),
    ("Ink 500", "#6B6353", "muted labels"),
    ("Ink 300", "#9A9081", "faint / disabled"),
    ("Paper", "#F4EFE2", "page background (cream)"),
    ("Paper 100", "#FBF8F0", "cards / panels"),
    ("Paper 200", "#EFE8D6", "hover / headers"),
    ("Paper 300", "#E4DAC1", "borders on cream"),
    ("Credit", "#0A7D3C", "money in · settled · success"),
    ("Debit", "#B3261E", "money out · blocked · error"),
]

cols, cw, ch, gap = 3, 440, 150, 24
for i, (name, hexv, use) in enumerate(SW):
    cx = 48 + (i % cols) * (cw + gap)
    cy = y + (i // cols) * (ch + gap)
    # ledger offset shadow
    d.rectangle([cx + 6, cy + 6, cx + 150, cy + 110], fill=INK)
    d.rectangle([cx, cy, cx + 144, cy + 104], fill=hexv, outline=INK,
                width=2)
    d.text((cx + 162, cy + 8), name, font=mono(28, True), fill=INK)
    d.text((cx + 162, cy + 46), hexv.upper(), font=mono(26), fill=ACCENT)
    d.text((cx + 162, cy + 80), use, font=mono(17), fill="#6B6353")

fy = H - 90
d.line([48, fy, W - 48, fy], fill=INK, width=2)
d.text((48, fy + 22),
       "Fonts: Space Grotesk + IBM Plex Mono (Google Fonts, OFL — free).  "
       "Style: hard 1px ink borders · square corners · 4–6px offset shadow.",
       font=mono(18), fill="#3A352C")

out = ("c:/Users/Vigan/OneDrive/Desktop/github-projects/Hermesx402/"
       "hermesx402-brand.png")
img.save(out)
print("saved", out, img.size)
