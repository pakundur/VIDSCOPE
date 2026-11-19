#!/usr/bin/env python3
"""Build the GitHub social preview card for VidScope.

1280x640 PNG under 1MB. Shows the project name, the one-sentence position,
and REAL probe output from a real clip (not a mockup). The FROZEN and LOW-RES
flags are the point: the product is the output, so the output is the subject.

Every x position is measured with getlength() rather than estimated, and the
layout is asserted before drawing. Two earlier versions shipped real bugs:
  v1 overflowed the code panel by 240px and ran through the accuracy strip.
  v2 used a magic 1.55 multiplier for label offsets, which put the tagline
     23px INSIDE the last stat. A vision check said "no collision" because
     the overlap is subtle at small scale; getlength() said otherwise.
Trust the measurement, not the eyeball.

Also keeps the left margin thick: GitHub's preview box crops/zooms the image
on narrow viewports, and the first version lost the "VidScope" title.
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
BG = (13, 17, 23)
PANEL = (22, 27, 34)
BORDER = (48, 54, 61)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
GREEN = (63, 185, 80)
AMBER = (210, 153, 34)
RED = (248, 81, 73)
CYAN = (121, 192, 255)

FONT = "/system/fonts/DroidSansMono.ttf"
OUT = pathlib.Path.home() / "repos/vidscope/docs/social-preview.png"

# Thick left margin so a centre-crop on mobile still shows the title.
PAD = 72

# ---- header ----
HEAD_Y = 34
TITLE_FS = 48
SUB_Y = 96
SUB_FS = 21

# ---- code panel ----
PX = PAD
PY = 148
PW = W - 2 * PAD
CODE_FS = 17
LH = 25
CODE_PAD_L = 26
CODE_TOP = PY + 52

LINES = [
    ('{',                                                          MUTED, 0),
    ('  "clips": { "duration_s": 23.321, "display_width": 480,',   CYAN, 0),
    ('  "scene": { "frames_scored": 582, "cuts_detected": 9,',     CYAN, 0),
    ('             "cuts_per_minute": 23.2 },',                    CYAN, 0),
    ('  "black": [],',                                             CYAN, 0),
    ('  "freeze": [ { "start": 20.321, "duration": 3.0,',          CYAN, 0),
    ('                "runs_to_eof": true } ],',                   CYAN, 0),
    ('  "flags": [',                                               CYAN, 0),
    ('    "FROZEN — 3.0s at 20.3s; viewers read this as buffering",', RED, 0),
    ('    "LOW-RES — 480x854; upscaling will look soft"',          AMBER, 0),
    ('  ]',                                                        CYAN, 0),
    ('}',                                                          MUTED, 0),
]

PH = CODE_TOP - PY + len(LINES) * LH + 18

# ---- accuracy strip ----
STATS = [
    ("91/91", "cut precision"),
    ("30/30", "cut recall"),
    ("0/20",  "black+freeze mistakes"),
]
STAT_FS = 27
LBL_FS = 15
TAIL_FS = 14
TAIL = "every claim measured, every limit documented"

STRIP_Y = PY + PH + 26
GUTTER = 46          # gap between stat groups
TAIL_GAP = 36        # minimum gap before the tagline


def font(s):
    return ImageFont.truetype(FONT, s)


f_code, f_stat, f_lbl, f_tail = font(CODE_FS), font(STAT_FS), font(LBL_FS), font(TAIL_FS)

# ================= layout: measure, then assert =================

# 1. code lines fit inside the panel
code_bottom = CODE_TOP + len(LINES) * LH
assert code_bottom <= PY + PH - 8, f"code overflows panel by {code_bottom-(PY+PH)}px"
for txt, _, ind in LINES:
    right = PX + CODE_PAD_L + ind + f_code.getlength(txt)
    assert right <= PX + PW - 14, f"line too wide ({right:.0f} > {PX+PW-14}): {txt[:44]}"

# 2. stat groups laid out left to right with a real gutter
stat_x = []
cx = PX
for big, label in STATS:
    stat_x.append(cx)
    big_w = f_stat.getlength(big)
    lbl_w = f_lbl.getlength(label)
    # label sits just right of the big number, baseline-aligned
    group_w = big_w + 12 + lbl_w
    cx += group_w + GUTTER

last_end = (stat_x[-1] + f_stat.getlength(STATS[-1][0]) + 12
            + f_lbl.getlength(STATS[-1][1]))

# 3. tagline must CL EAR the last stat, measured, not guessed
tail_w = f_tail.getlength(TAIL)
tail_x = W - PAD - tail_w
gap = tail_x - last_end
assert gap >= TAIL_GAP, (
    f"tagline collides with last stat: gap {gap:.0f}px < {TAIL_GAP}px "
    f"(last stat ends {last_end:.0f}, tagline starts {tail_x:.0f})")

# 4. everything fits vertically
assert STRIP_Y + 34 <= H - 8, f"strip overflows canvas ({STRIP_Y+34} > {H-8})"

# ================= draw =================
img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

d.text((PAD, HEAD_Y), "VidScope", font=font(TITLE_FS), fill=TEXT)
d.text((PAD, SUB_Y), "Video forensics a script can trust:", font=font(SUB_FS), fill=MUTED)

d.rounded_rectangle([PX, PY, PX + PW, PY + PH], radius=10,
                    fill=PANEL, outline=BORDER, width=2)
for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    d.ellipse([PX + 20 + i * 22, PY + 14, PX + 31 + i * 22, PY + 25], fill=col)
d.text((PX + 100, PY + 12), "vidscope probe --json", font=font(15), fill=MUTED)

y = CODE_TOP
for txt, col, ind in LINES:
    d.text((PX + CODE_PAD_L + ind, y), txt, font=f_code, fill=col)
    y += LH

# stats, measured positions
for (big, label), x in zip(STATS, stat_x):
    d.text((x, STRIP_Y), big, font=f_stat, fill=GREEN)
    d.text((x + f_stat.getlength(big) + 12, STRIP_Y + 8), label, font=f_lbl, fill=MUTED)

d.text((tail_x, STRIP_Y + 9), TAIL, font=f_tail, fill=MUTED)

img.save(OUT, "PNG", optimize=True)
size = OUT.stat().st_size
print(f"wrote {OUT}")
print(f"  {img.size[0]}x{img.size[1]}  {size/1024:.0f} KB  under1MB={size < 1024*1024}")
print(f"  code_bottom={code_bottom}  panel_bottom={PY+PH}  strip_y={STRIP_Y}")
print(f"  last stat ends {last_end:.0f}px, tagline starts {tail_x:.0f}px, gap {gap:.0f}px")
print("  all assertions passed")
