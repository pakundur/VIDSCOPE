#!/usr/bin/env python3
"""
vd_sheet.py — build frame contact sheets from a video for vision analysis.

Rungs (same discipline as tiktok-affiliate-voiceover, generalised):
  rung 1  overview   330px cells, ~1fps spread across the WHOLE clip
  rung 2  inspect    760px cells, chosen timestamps -> product framing, text
  rung 3  fullres    1080px, exact ship timestamps -> confirm any suspect label

Usage:
  python3 vd_sheet.py FILE --rung 1
  python3 vd_sheet.py FILE --rung 2
  python3 vd_sheet.py FILE --rung 3 --times 0.5 4.2 11.8
  python3 vd_sheet.py FILE --rung 2 --grid 3x3 --out /path/sheet.jpg
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUNGS = {
    1: {"cell": 330, "grid": "4x4"},
    2: {"cell": 760, "grid": "3x3"},
    3: {"cell": 1080, "grid": "2x2"},
}

# Seek precision. `-ss` before `-i` is fast because it seeks to a keyframe, but
# on some containers/codecs it can return a frame up to a GOP early. For rung 3
# -- where the whole point is reading a label -- we cannot afford that, so we
# seek AFTER `-i` (decode from the start, drop frames until the timestamp).
# That is slower but exact. Rungs 1-2 are overview only, so fast seek is fine.
EXACT_SEEK_RUNGS = {3}


def probe_duration(path):
    p = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def auto_times(dur, n):
    """Spread n samples across the WHOLE clip, including both ends.

    A mid-clip-only sheet misses the first and last frame — where hooks and
    payoff live. Always include t=0 and one frame just before the end.

    Note: this must be used for rung 1 too. Naive `range(int(dur/step))[:n]`
    only ever samples the first n seconds, so a 130s clip was represented by
    its first 16s and 88% of the video was never looked at.
    """
    if dur <= 0:
        return [0.0]
    if n <= 1:
        return [0.0]
    last = max(0.0, dur - 0.15)
    return [round(i * last / (n - 1), 3) for i in range(n)]


def clamp_times(times, dur):
    """Keep requested times inside the clip; report any that had to move."""
    out, adjusted = [], []
    for t in times:
        t = max(0.0, float(t))
        if dur and t > dur - 0.05:
            new = round(max(0.0, dur - 0.15), 3)
            adjusted.append({"requested": round(t, 3), "used": new})
            t = new
        out.append(round(t, 3))
    return out, adjusted


def extract_frame(path, t, dest, cell, exact):
    """Extract one frame at t. Returns True on success, False otherwise.

    We do NOT try to reverse-engineer the exact decoded timestamp: ffprobe on
    a single extracted JPEG reports 0, so any "actual time" we printed would be
    invented. Honesty rule: the sidecar lists only the frames that actually
    landed in the image, in cell order, and separately lists failures. That is
    enough to keep labels truthful without fabricating precision.
    """
    if exact:
        # -ss AFTER -i: decode-accurate, no keyframe snap
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(path), "-ss", f"{t}", "-frames:v", "1"]
    else:
        # -ss BEFORE -i: fast keyframe seek
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", f"{t}", "-i", str(path), "-frames:v", "1"]

    # scale shortest side to `cell` so LANDSCAPE footage is not crushed to
    # 1080x608 at the one rung whose job is reading a label
    cmd += ["-vf", f"scale=-2:{cell}", str(dest)]
    subprocess.run(cmd, capture_output=True)
    return dest.exists() and dest.stat().st_size > 0


def build(path, rung, times=None, grid=None, out=None):
    path = Path(path)
    if not path.exists():
        print(json.dumps({"error": f"not found: {path}"}))
        return None
    cfg = RUNGS[rung]
    cell = cfg["cell"]
    grid = grid or cfg["grid"]
    cols, rows = (int(x) for x in grid.lower().split("x"))
    n = cols * rows
    dur = probe_duration(path)
    exact = rung in EXACT_SEEK_RUNGS

    if not times:
        times = auto_times(dur, n)
    requested = [round(float(t), 3) for t in times][:n]
    times, adjusted = clamp_times(requested, dur)

    tmpdir = Path(tempfile.mkdtemp(prefix="vd_sheet_"))
    try:
        return _build_tiles(path, tmpdir, times, cell, cols, rows, out,
                            dur, rung, grid, exact, requested, adjusted)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_tiles(path, tmpdir, times, cell, cols, rows, out, dur, rung, grid,
                 exact, requested, adjusted):
    stills = []
    actual_times = []
    failed = []

    for i, t in enumerate(times):
        sp = tmpdir / f"s{i:03d}.jpg"
        if extract_frame(path, t, sp, cell, exact):
            stills.append(sp)
            actual_times.append(t)
        else:
            failed.append(t)

    if not stills:
        print(json.dumps({"error": "no frames extracted",
                          "requested_times": requested}))
        return None

    out = Path(out) if out else path.parent / f"{path.stem}_rung{rung}.jpg"

    if len(stills) == 1:
        # tile=4x4 on a single frame fails; just copy the still out
        shutil.copyfile(stills[0], out)
    else:
        lst = tmpdir / "list.txt"
        with lst.open("w") as fh:
            for sp in stills:
                fh.write(f"file '{sp}'\nduration 1\n")
            fh.write(f"file '{stills[-1]}'\n")
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(lst),
            # scale=-2:{cell} here too: if this stage pinned WIDTH it would
            # silently re-scale the tiles and mask a wrong per-frame scale,
            # which is how the landscape bug hid from a naive check.
            "-vf", f"scale=-2:{cell},tile={cols}x{rows}:padding=4:margin=4:color=black",
            "-frames:v", "1", str(out),
        ], capture_output=True)

    if not out.exists():
        print(json.dumps({"error": "tile failed"}))
        return None

    meta = {
        "sheet": str(out),
        "rung": rung,
        "cell_px": cell,
        "grid": grid,
        "duration_s": round(dur, 2),
        # times is what is ACTUALLY in the image, in cell order.
        # requested_times is what the caller asked for. They differ if a seek
        # failed or a time was clamped -- never label cells from the request.
        "times": actual_times,
        "requested_times": requested,
        "cells_filled": len(stills),
        "cells_expected": cols * rows,
        "seek_mode": "decode-accurate" if exact else "keyframe",
        "bytes": out.stat().st_size,
    }
    if adjusted:
        meta["clamped"] = adjusted
    if failed:
        meta["failed_seeks"] = failed
        meta["warning"] = (
            f"{len(failed)} requested time(s) could not be extracted; "
            f"'times' lists only frames actually in the sheet, in order"
        )

    (out.with_suffix(".json")).write_text(json.dumps(meta, indent=2))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--rung", type=int, default=1, choices=[1, 2, 3])
    ap.add_argument("--times", nargs="*", type=float)
    ap.add_argument("--grid")
    ap.add_argument("--out")
    a = ap.parse_args()
    m = build(a.file, a.rung, a.times, a.grid, a.out)
    if m:
        print(json.dumps(m, indent=2))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
