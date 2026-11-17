#!/usr/bin/env python3
"""
vd_sheet.py — build frame contact sheets from a video for vision analysis.

Rungs (same discipline as tiktok-affiliate-voiceover, generalised):
  rung 1  overview   330px cells, ~1fps  -> "what is this video?" (fast, cheap)
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
    1: {"cell": 330, "every": 1.0, "grid": "4x4"},
    2: {"cell": 760, "every": 0.0, "grid": "3x3"},   # every->use --times
    3: {"cell": 1080, "every": 0.0, "grid": "2x2"},
}


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
    """Spread n samples so BOTH ends are included.

    A mid-clip-only sheet misses the first and last frame — where hooks and
    payoff live. Always include t=0 and one frame just before the end.
    """
    if dur <= 0:
        return [0.0]
    if n <= 1:
        return [0.0]
    last = max(0.0, dur - 0.15)
    return [round(i * last / (n - 1), 3) for i in range(n)]


def build(path, rung, times=None, grid=None, out=None, label=True):
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

    if not times:
        if rung == 1:
            step = cfg["every"] or 1.0
            times = [round(i * step, 3) for i in range(int(dur / step) + 1)][:n]
            while len(times) < n:
                times.append(times[-1] if times else 0.0)
        else:
            times = auto_times(dur, n)
    times = times[:n]

    # f=image2 over a generated list is unreliable; use select on exact times
    # via trim per input. Cleanest portable route: extract each still, then tile.
    # Use a system temp dir, NOT a dir next to the input -- the input may be on a
    # read-only mount (mounted archive, network share, camera roll).
    tmpdir = Path(tempfile.mkdtemp(prefix="vd_sheet_"))
    try:
        return _build_tiles(path, tmpdir, times, cell, cols, rows, out, dur, rung, grid)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_tiles(path, tmpdir, times, cell, cols, rows, out, dur, rung, grid):
    stills = []
    for i, t in enumerate(times):
        sp = tmpdir / f"s{i:03d}.jpg"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{t}", "-i", str(path), "-frames:v", "1",
            "-vf", f"scale={cell}:-2",
            str(sp),
        ], capture_output=True)
        if sp.exists() and sp.stat().st_size > 0:
            stills.append(sp)

    if not stills:
        print(json.dumps({"error": "no frames extracted"}))
        return None

    out = Path(out) if out else path.parent / f"{path.stem}_rung{rung}.jpg"
    # tile via concat of stills using a virtual sequence
    lst = tmpdir / "list.txt"
    with lst.open("w") as fh:
        for sp in stills:
            fh.write(f"file '{sp}'\n")
            # pad to exactly one frame each
            fh.write("duration 1\n")
        fh.write(f"file '{stills[-1]}'\n")
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-vf", f"scale={cell}:-2,tile={cols}x{rows}:padding=4:margin=4:color=black",
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
        "times": times,
        "bytes": out.stat().st_size,
    }
    # sidecar so the vision prompt can name timestamps precisely
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
    print(json.dumps(m, indent=2) if m else "")


if __name__ == "__main__":
    main()
