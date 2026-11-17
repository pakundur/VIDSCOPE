#!/usr/bin/env python3
"""Adversarial test harness for vidscope. Tries to break it."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "scripts" / "vidscope"
PY = sys.executable

results = []


def rec(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  <- {detail}" if detail and not ok else ""))


def run(args, stdin=None, timeout=120):
    return subprocess.run([PY, str(CLI), *args], capture_output=True,
                          text=True, input=stdin, timeout=timeout)


def ff(*args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="vdtest_"))
    src = Path.home() / "folders" / "kitchen_clips" / "k01.mp4"
    if not src.exists():
        print("no source clip; abort")
        return

    # ---------- 1. nonexistent file
    r = run(["probe", str(tmp / "nope.mp4"), "--json"])
    try:
        d = json.loads(r.stdout)
        rec("missing file -> JSON error", "error" in d, str(d)[:120])
    except Exception as e:
        rec("missing file -> JSON error", False, f"unparseable stdout: {r.stdout[:100]!r} {e}")

    # ---------- 2. not a video at all
    fake = tmp / "fake.mp4"
    fake.write_text("this is not a video")
    r = run(["probe", str(fake), "--json"])
    ok = False
    try:
        d = json.loads(r.stdout)
        ok = "error" in d or d.get("clips", {}).get("video") is None
    except Exception:
        ok = r.returncode != 0
    rec("non-video file handled", ok, f"rc={r.returncode} out={r.stdout[:100]!r}")

    # ---------- 3. zero-byte file
    empty = tmp / "empty.mp4"
    empty.write_bytes(b"")
    r = run(["probe", str(empty), "--json"])
    ok = r.returncode != 0 or "error" in r.stdout
    rec("zero-byte file handled", ok, f"rc={r.returncode}")

    # ---------- 4. ultra-short clip (1 frame)
    one = tmp / "one.mp4"
    ff("-i", str(src), "-frames:v", "1", "-an", str(one))
    r = run(["probe", str(one), "--json"])
    ok = r.returncode == 0
    if ok:
        d = json.loads(r.stdout)
        dur = d["clips"]["duration_s"]
        # a single frame should not be reported as a long clip
        ok = dur < 1.5
        rec("1-frame clip", ok, f"duration={dur}")

    # ---------- 5. audio-only file (no video stream)
    aud = tmp / "aud.m4a"
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "aac", str(aud))
    r = run(["probe", str(aud), "--json"])
    try:
        d = json.loads(r.stdout)
        # must not crash; video will be None
        rec("audio-only file", d.get("clips", {}).get("video") is None,
            f"video={d.get('clips',{}).get('video')}")
    except Exception as e:
        rec("audio-only file", False, f"{e} out={r.stdout[:100]!r}")

    # ---------- 6. sheet on a 1-frame clip (auto_times edge)
    if one.exists():
        r = run(["sheet", str(one), "--rung", "2", "--out", str(tmp / "s_one.jpg")])
        ok = (tmp / "s_one.jpg").exists() or "error" in r.stdout
        rec("sheet on 1-frame clip", ok, r.stdout[:100])

    # ---------- 7. sheet --times with MORE times than grid cells
    r = run(["sheet", str(src), "--rung", "1", "--times"] +
            [str(i) for i in range(30)] + ["--out", str(tmp / "s_many.jpg")])
    ok = r.returncode == 0
    rec("sheet with 30 times on 4x4 grid", ok, r.stdout[:150])

    # ---------- 8. sheet --times out of range (beyond duration)
    r = run(["sheet", str(src), "--rung", "2", "--times", "999", "1000",
             "--out", str(tmp / "s_oor.jpg")])
    ok = r.returncode == 0
    produced = (tmp / "s_oor.jpg").exists()
    rec("sheet with out-of-range times", ok, f"rc={r.returncode} produced={produced}")

    # ---------- 9. brief on a clip shorter than target band
    r = run(["brief", str(one)])
    ok = r.returncode == 0 and "Target" in r.stdout
    rec("brief on 1-frame clip", ok, r.stdout[:120])

    # ---------- 10. brief --target reversed (hi < lo)
    r = run(["brief", str(src), "--target", "34", "21"])
    ok = r.returncode == 0
    rec("brief reversed target band", ok, f"rc={r.returncode}")

    # ---------- 11. unicode / spaces in path
    sp = tmp / "clip with spaces ünïcode.mp4"
    ff("-i", str(src), "-t", "2", "-c", "copy", str(sp))
    if sp.exists():
        r = run(["probe", str(sp), "--json"])
        ok = r.returncode == 0
        rec("unicode + spaces in path", ok, r.stdout[:120])

    # ---------- 12. rotation metadata must actually be READ, and must flip
    # orientation. The original test only asserted rc==0, which is exactly how
    # the ffmpeg-8 side_data bug hid: the field stayed None and nothing failed.
    rot = tmp / "rot.mp4"
    ff("-display_rotation", "90", "-i", str(src), "-t", "2", "-c", "copy", str(rot))
    r = run(["probe", str(rot), "--json"])
    ok = False
    detail = ""
    if r.returncode == 0:
        d = json.loads(r.stdout)
        c = d["clips"]
        v = c.get("video") or {}
        has_rot = v.get("rotation") in (90, -90, 270)
        flipped = (c.get("display_width"), c.get("display_height")) == (
            v.get("height"), v.get("width"))
        aspect_flagged = any("ASPECT" in f for f in d["flags"])
        ok = has_rot and flipped and aspect_flagged
        detail = (f"rotation={v.get('rotation')} "
                  f"display={c.get('display_width')}x{c.get('display_height')} "
                  f"stored={v.get('width')}x{v.get('height')} "
                  f"aspect_flag={aspect_flagged}")
    rec("rotation read + orientation flipped", ok, detail or f"rc={r.returncode}")

    # ---------- 13. variable frame rate / unusual fps
    vfr = tmp / "vfr.mp4"
    ff("-i", str(src), "-t", "3", "-vf", "fps=12", str(vfr))
    r = run(["probe", str(vfr), "--json"])
    ok = r.returncode == 0 and json.loads(r.stdout)["clips"]["video"]["fps"] > 0
    rec("low fps clip (12fps)", ok, r.stdout[:100])

    # ---------- 14. stdout must be CLEAN JSON (no ffmpeg noise) with --json
    r = run(["probe", str(src), "--json"])
    ok = True
    try:
        json.loads(r.stdout)
    except Exception:
        ok = False
    rec("--json stdout is pure JSON", ok, f"len={len(r.stdout)} first={r.stdout[:60]!r}")

    # ---------- 15. unknown command
    r = run(["frobnicate"])
    rec("unknown command -> nonzero exit", r.returncode != 0, f"rc={r.returncode}")

    # ---------- 16. no args
    r = run([])
    rec("no args -> help, exit 0", r.returncode == 0 and "usage" in r.stdout.lower(),
        f"rc={r.returncode}")

    # ---------- 17. brief via stdin JSON '-'
    p = subprocess.run([PY, str(REPO / "scripts" / "vd_probe.py"), str(src), "--json"],
                       capture_output=True, text=True)
    r = subprocess.run([PY, str(REPO / "scripts" / "vd_brief.py"), "-"],
                       input=p.stdout, capture_output=True, text=True)
    rec("vd_brief reads '-' from stdin", r.returncode == 0 and "Video brief" in r.stdout,
        r.stderr[:150])

    # ---------- 18. concurrent sheet runs must not collide (temp dir isolation)
    outs = []
    for i in range(3):
        o = tmp / f"conc{i}.jpg"
        outs.append(subprocess.Popen(
            [PY, str(CLI), "sheet", str(src), "--rung", "1", "--out", str(o)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for p_ in outs:
        p_.wait(timeout=180)
    made = sum(1 for i in range(3) if (tmp / f"conc{i}.jpg").exists())
    rec("3 concurrent sheets", made == 3, f"{made}/3 produced")

    # ---------- 19. freeze AT EOF must be reported.
    # ffmpeg emits only freeze_start when the freeze never ends, so a static
    # clip used to parse as clean. This is the case that matters most: a video
    # that stops moving before it stops playing reads as a hang.
    still = tmp / "still.mp4"
    ff("-f", "lavfi", "-i", "color=blue:s=720x1280:d=3", str(still))
    r = run(["probe", str(still), "--json"])
    ok = False
    detail = ""
    if r.returncode == 0:
        d = json.loads(r.stdout)
        fr = d["freeze"]
        flagged = any("FROZEN" in f for f in d["flags"])
        ok = bool(fr) and flagged
        detail = f"freeze={fr} flags={[f for f in d['flags'] if 'FROZEN' in f]}"
    rec("freeze running to EOF is reported", ok, detail or f"rc={r.returncode}")

    # ---------- 20. freeze that ENDS mid-clip still reported (no regression)
    fe = tmp / "freeze_ends.mp4"
    ff("-f", "lavfi", "-i", "color=blue:s=720x1280:d=2",
       "-f", "lavfi", "-i", "testsrc=s=720x1280:d=1:r=30",
       "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", str(fe))
    r = run(["probe", str(fe), "--json"])
    ok = False
    detail = ""
    if r.returncode == 0:
        d = json.loads(r.stdout)
        fr = d["freeze"]
        ok = bool(fr) and fr[0].get("duration") and fr[0]["duration"] >= 1.5
        detail = f"freeze={fr}"
    rec("freeze ending mid-clip still reported", ok, detail or f"rc={r.returncode}")

    # ---------- 21. pure black: crushed count must equal dark count (not 0, not all)
    blk = tmp / "black.mp4"
    ff("-f", "lavfi", "-i", "color=black:s=320x240:d=1,format=yuv420p", str(blk))
    r = run(["probe", str(blk), "--json"])
    ok = False
    detail = ""
    if r.returncode == 0:
        d = json.loads(r.stdout)
        lm = d["luma"]
        ok = lm["crushed_black_frames"] == lm["samples"] and lm["samples"] > 0
        detail = f"crushed={lm['crushed_black_frames']} samples={lm['samples']}"
    rec("pure black counts as crushed", ok, detail or f"rc={r.returncode}")

    # ---------- 22. brief must not claim 'drop 0' when the source is too short
    r = run(["brief", str(still), "--target", "21", "34"])
    line = next((l for l in r.stdout.splitlines() if l.startswith("**Target")), "")
    ok = "too short" in line and "drop 0" not in line
    rec("brief is honest about short source", ok, line[:140])

    print("\n" + "=" * 60)
    failed = [r_ for r_ in results if not r_[1]]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("\nFAILURES:")
        for n, _, d in failed:
            print(f"  - {n}: {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
