#!/usr/bin/env python3
"""
vd_brief.py — turn vd_probe.py output into a content brief + segment plan.

Reads the JSON from vd_probe.py and produces:
  - a human/LLM-readable brief (structure, pacing, likely segment boundaries)
  - a segment plan for re-cutting (start/end per beat)
  - a vision prompt pre-filled with the exact timestamps of the frames

Usage:
  python3 vd_probe.py FILE --json > probe.json
  python3 vd_brief.py probe.json
  python3 vd_brief.py probe.json --target 21 34
"""
import argparse
import json
import sys
from pathlib import Path


def fmt(t):
    return f"{t:6.2f}s"


def segment_plan(probe, target_lo=None, target_hi=None):
    """Propose cuts at the strongest scene boundaries, respecting a target length."""
    cuts = [c["time"] for c in probe.get("scene", {}).get("top_cuts", [])]
    dur = probe.get("clips", {}).get("duration_s", 0) or 0
    bounds = sorted(set([0.0] + cuts + [round(dur, 2)]))
    segs = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a >= 0.8:            # ignore sub-0.8s slivers
            segs.append({"start": round(a, 2), "end": round(b, 2),
                         "len": round(b - a, 2)})

    plan = {"n_segments": len(segs), "segments": segs}

    if target_lo and target_hi:
        # greedy: take segments in order until we land inside the band
        chosen, total = [], 0.0
        for s in segs:
            if total >= target_lo:
                break
            if total + s["len"] <= target_hi:
                chosen.append(s)
                total += s["len"]
        plan["target"] = {"lo": target_lo, "hi": target_hi,
                          "achieved": round(total, 2),
                          "in_band": target_lo <= total <= target_hi,
                          "kept": len(chosen), "dropped": len(segs) - len(chosen)}
        plan["recommended"] = chosen
    return plan


def build_brief(probe, segplan):
    c = probe.get("clips", {})
    v = c.get("video") or {}
    sc = probe.get("scene", {})
    lum = probe.get("luma", {})
    L = []
    L.append(f"# Video brief — {c.get('file','?')}")
    L.append("")
    L.append(f"- **Duration:** {c.get('duration_s',0):.2f}s")
    L.append(f"- **Resolution:** {v.get('width')}x{v.get('height')} "
             f"({c.get('orientation','?')}) @ {v.get('fps')}fps, {v.get('codec')}")
    L.append(f"- **Audio streams:** {c.get('audio_streams',0)}"
             + ("  (SILENT)" if c.get("audio_streams") == 0 else ""))
    L.append(f"- **Size:** {c.get('size_mb')} MB, {c.get('bitrate_kbps')} kbps")
    L.append("")

    # pacing
    cuts = sc.get("cuts_detected", 0)
    dur = c.get("duration_s", 1) or 1
    cpm = cuts / (dur / 60) if dur else 0
    L.append("## Structure & pacing")
    L.append("")
    L.append(f"- **Scene cuts detected:** {cuts} "
             f"(**{cpm:.0f} cuts/min**)")
    if cpm < 6:
        L.append("  - single continuous take or very few cuts; treat as ONE shot")
    elif cpm < 20:
        L.append("  - normal dialogue/demo pacing")
    else:
        L.append("  - fast-cut montage; each cut is ~"
                 f"{dur/max(cuts,1):.1f}s")
    if sc.get("top_cuts"):
        L.append("- **Strongest boundaries (best cut points):** "
                 + ", ".join(fmt(t["time"]) for t in sc["top_cuts"][:8]))
    L.append("")

    # exposure / quality
    L.append("## Image quality")
    L.append("")
    L.append(f"- Mean luma {lum.get('y_avg_mean')}/255 "
             f"(range {lum.get('y_avg_min')}–{lum.get('y_avg_max')})")
    L.append(f"- Crushed blacks: {lum.get('crushed_black_frames',0)} frames · "
             f"Blown highlights: {lum.get('blown_white_frames',0)} · "
             f"Dark frames: {lum.get('dark_frames',0)}")
    L.append("")

    # defects
    if probe.get("black") or probe.get("freeze"):
        L.append("## Defects")
        L.append("")
        for b in probe.get("black", []):
            L.append(f"- **BLACK** {b['duration']:.1f}s @ {b['start']:.1f}s–{b['end']:.1f}s")
        for f in probe.get("freeze", []):
            L.append(f"- **FROZEN** {f.get('duration')}s @ {f.get('start')}s")
        L.append("")

    # flags
    if probe.get("flags"):
        L.append("## Action required")
        L.append("")
        for f in probe["flags"]:
            L.append(f"- {f}")
        L.append("")

    # segments
    sp = segplan
    L.append(f"## Segment plan ({sp['n_segments']} candidate beats)")
    L.append("")
    L.append("| # | start | end | len |")
    L.append("|---|-------|-----|-----|")
    for i, s in enumerate(sp["segments"], 1):
        L.append(f"| {i} | {s['start']:.2f}s | {s['end']:.2f}s | {s['len']:.2f}s |")
    L.append("")
    if "target" in sp:
        t = sp["target"]
        L.append(f"**Target {t['lo']}–{t['hi']}s:** achieved {t['achieved']}s "
                 f"({'IN BAND' if t['in_band'] else 'OUT OF BAND'}) — "
                 f"keep {t['kept']} beats, drop {t['dropped']}")
        L.append("")

    # vision prompt
    times = []
    for s in (sp.get("recommended") or sp["segments"])[:8]:
        times.append(round((s["start"] + s["end"]) / 2, 2))
    L.append("## Vision prompt (paste with the rung-2 sheet)")
    L.append("")
    L.append("```")
    L.append(f"This is a contact sheet from a {dur:.1f}s video, one frame every ~"
             f"{dur/max(len(times),1):.1f}s, at these timestamps: {times}.")
    L.append("Describe in order: (1) what physically happens, beat by beat;")
    L.append("(2) is there a BEFORE (problem/mess/dirty) state and an AFTER (payoff/clean) state;")
    L.append("(3) any readable on-screen text, logos, brand names, or human faces —")
    L.append("    name the exact frame and the exact letters you can read;")
    L.append("(4) what single product is being demonstrated.")
    L.append("Be literal. If you cannot read actual letters, say 'no text'.")
    L.append("```")
    L.append("")
    L.append("> Text reported here is a LEAD, not a finding. Zoom to full-res "
             "(rung 3) on any suspect frame before acting on it.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("probe_json")
    ap.add_argument("--target", nargs=2, type=float, metavar=("LO", "HI"),
                    default=[21.0, 34.0])
    ap.add_argument("--out")
    a = ap.parse_args()

    p = Path(a.probe_json)
    raw = sys.stdin.read() if str(p) == "-" else p.read_text()
    probe = json.loads(raw)
    if probe.get("error"):
        print(probe["error"])
        sys.exit(1)

    segplan = segment_plan(probe, a.target[0], a.target[1])
    brief = build_brief(probe, segplan)
    if a.out:
        Path(a.out).write_text(brief)
        print(f"wrote {a.out}")
    else:
        print(brief)


if __name__ == "__main__":
    main()
