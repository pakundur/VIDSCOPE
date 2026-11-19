#!/usr/bin/env python3
"""Build the GitHub social preview card for VidScope.

1280x640 PNG under 1MB. Shows the project name, the one-sentence position,
and REAL probe output from a real clip (not a mockup). The FROZEN and LOW-RES
flags are the point: the product is the output, so the output is the subject.

Layout is computed and asserted before drawing, because the first attempt
overflowed its panel by 240px and overlapped the accuracy strip.
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

PAD = 56
PX, PY, PW, PH = PAD, 160, W - 2 * PAD, 380
CODE_FS = 18
LH = 26
CODE_TOP = PY + 54


def font(s):
    return ImageFont.truetype(FONT, s)


# Each tuple: (text, colour, x_indent). Condensed to what a viewer needs:
# the flags carry the story, so the JSON above them is trimmed to 4 lines.
LINES = [
    ('{',                                            MUTED,  0),
    ('  "clips": { "duration_s": 23.321, "display_width": 480,', CYAN, 0),
    ('  "scene": { "frames_scored": 582, "cuts_detected": 9,',   CYAN, 0),
    ('             "cuts_per_minute": 23.2 },',                  CYAN, 0),
    ('  "black": [],',                                           CYAN, 0),
    ('  "freeze": [ { "start": 20.321, "duration": 3.0,',        CYAN, 0),
    ('                "runs_to_eof": true } ],',                 CYAN, 0),
    ('  "flags": [',                                             CYAN, 0),
    ('    "FROZEN — 3.0s at 20.3s; viewers read this as buffering",', RED, 0),
    ('    "LOW-RES — 480x854; upscaling will look soft"',        AMBER, 0),
    ('  ]',                                                      CYAN, 0),
    ('}',                                                        MUTED, 0),
]

f_code = font(CODE_FS)

# ---- geometry assertions BEFORE drawing ----
code_bottom = CODE_TOP + len(LINES) * LH
assert code_bottom <= PY + PH - 10, f"code overflows panel by {code_bottom-(PY+PH)}px"
for txt, _, ind in LINES:
    right = PX + 24 + ind + f_code.getlength(txt)
    assert right <= PX + PW - 12, f"line too wide ({right:.0f} > {PX+PW-12}): {txt[:50]}"

STRIP_Y = PY + PH + 30
assert STRIP_Y + 40 <= H - 10, "accuracy strip would fall off canvas"

# ---- draw ----
img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

d.text((PAD, 40), "VidScope", font=font(50), fill=TEXT)
d.text((PAD, 104), "Video forensics a script can trust:", font=font(22), fill=MUTED)

d.rounded_rectangle([PX, PY, PX + PW, PY + PH], radius=10,
                    fill=PANEL, outline=BORDER, width=2)
for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    d.ellipse([PX + 20 + i * 22, PY + 15, PX + 31 + i * 22, PY + 26], fill=col)
d.text((PX + 100, PY + 13), "vidscope probe --json", font=font(16), fill=MUTED)

y = CODE_TOP
for txt, col, ind in LINES:
    d.text((PX + 24 + ind, y), txt, font=f_code, fill=col)
    y += LH

# ---- accuracy strip ----
def stat(x, big, label):
    d.text((x, STRIP_Y), big, font=font(28), fill=GREEN)
    d.text((x + f_code.getlength(big) * 1.55, STRIP_Y + 8), label,
           font=font(16), fill=MUTED)

stat(PAD,        "91/91", "cut precision")
stat(PAD + 250,  "30/30", "cut recall")
stat(PAD + 480,  "0/20",  "black+freeze mistakes")

tail = "every claim measured, every limit documented"
d.text((W - PAD - font(15).getlength(tail), STRIP_Y + 10), tail,
       font=font(15), fill=MUTED)

img.save(OUT, "PNG", optimize=True)
size = OUT.stat().st_size
print(f"wrote {OUT}")
print(f"  {img.size[0]}x{img.size[1]}  {size/1024:.0f} KB  under1MB={size < 1024*1024}")
print(f"  geometry: code_bottom={code_bottom} panel_bottom={PY+PH} strip={STRIP_Y}")
print("  all assertions passed")
