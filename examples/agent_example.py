#!/usr/bin/env python3
"""
agent_example.py — drive VidScope from an AI agent.

Shows the intended agent loop:
  1. free signal pass (no model tokens)
  2. stop early if the file is broken
  3. build a sheet only at frames the detector says matter
  4. escalate every text claim to full resolution

Run:  python3 examples/agent_example.py path/to/clip.mp4
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
VIDSCOPE = HERE / "scripts" / "vidscope"


def run(*args, stdin=None):
    p = subprocess.run([sys.executable, str(VIDSCOPE), *args],
                       capture_output=True, text=True, input=stdin)
    if p.returncode != 0:
        raise RuntimeError(f"vidscope {' '.join(args)} failed:\n{p.stderr or p.stdout}")
    return p.stdout


def triage(video):
    """Step 1-2: free measurement, decide whether looking is even worth it."""
    probe = json.loads(run("probe", video, "--json"))
    clips = probe["clips"]
    v = clips.get("video") or {}

    print(f"{clips['file']}: {clips['duration_s']:.1f}s "
          f"{v.get('width')}x{v.get('height')} @ {v.get('fps')}fps")
    print(f"  scene cuts: {probe['scene']['cuts_detected']}  "
          f"audio streams: {clips['audio_streams']}")

    # Hard blockers: don't spend a vision call describing unusable footage.
    blockers = [f for f in probe["flags"] if f.startswith(("LOW-RES", "ASPECT"))]
    advisories = [f for f in probe["flags"] if f not in blockers]

    for f in advisories:
        print(f"  note: {f}")
    for f in blockers:
        print(f"  BLOCKER: {f}")
    return probe, blockers


def sample_points(probe, n=6):
    """Step 3: choose frames worth looking at.

    Prefer strong scene-cut boundaries (that is where content changes), then
    pad with evenly spaced points so both ends are always represented.
    """
    dur = probe["clips"]["duration_s"]
    cuts = [c["time"] for c in probe["scene"]["top_cuts"]][:n]
    pts = sorted({0.0, round(dur - 0.15, 2), *[round(t, 2) for t in cuts]})
    return pts[:n] if len(pts) >= n else pts


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    video = sys.argv[1]

    probe, blockers = triage(video)
    if blockers:
        print("\nStop: fix the blockers above before analysing content.")
        return

    pts = sample_points(probe)
    print(f"\nSampling {len(pts)} frames at: {pts}")

    out = Path(video).with_name(Path(video).stem + "_inspect.jpg")
    meta = json.loads(run("sheet", video, "--rung", "3",
                          "--times", *[str(t) for t in pts],
                          "--out", str(out)))
    print(f"Sheet: {meta['sheet']} ({meta['bytes']//1024} KB)")

    print("\nNext step (agent):")
    print(f'  vision("{meta["sheet"]}", question='
          f'"Describe what happens; list any readable text, naming the exact '
          f'frame; say \'no text\' if you cannot read letters.")')
    print("\nThen ESCALATE any text claim to a tighter crop before acting on it.")
    print("A rung-3 sheet is the last cheap check, not the final word.")


if __name__ == "__main__":
    main()
