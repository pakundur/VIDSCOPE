#!/usr/bin/env python3
"""
vd_probe.py — forensic probe of a video file. Emits JSON.

Pass 1  container/stream facts (ffprobe)
Pass 2  scene-change scores per frame (ffmpeg scdet)
Pass 3  black / freeze intervals (ffmpeg blackdetect, freezedetect)
Pass 4  per-frame luma + saturation (ffmpeg signalstats)

Usage:  python3 vd_probe.py FILE [--json]
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


# ---------------------------------------------------------------- pass 1
def probe_container(path):
    rc, out = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    if rc != 0:
        return {"error": "ffprobe failed"}
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        m = out.find("{")
        d = json.loads(out[m:]) if m >= 0 else {}

    fmt = d.get("format", {})
    info = {
        "file": Path(path).name,
        "duration_s": float(fmt.get("duration", 0) or 0),
        "size_mb": round(int(fmt.get("size", 0) or 0) / 1e6, 2),
        "bitrate_kbps": round(int(fmt.get("bit_rate", 0) or 0) / 1000),
        "format": fmt.get("format_name", ""),
        "streams": [],
        "video": None,
        "audio_streams": 0,
    }
    for s in d.get("streams", []):
        if s.get("codec_type") == "video":
            fr = s.get("r_frame_rate", "0/1")
            try:
                num, den = fr.split("/")
                fps = round(float(num) / float(den), 3) if float(den) else 0
            except (ValueError, ZeroDivisionError):
                fps = 0
            v = {
                "codec": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "fps": fps,
                "pix_fmt": s.get("pix_fmt"),
                "nb_frames": s.get("nb_frames"),
                "duration_s": float(s.get("duration", 0) or 0),
                "display_aspect_ratio": s.get("display_aspect_ratio"),
                # rotation matters: phone clips often carry a 90/270 matrix
                "rotation": int(float(
                    (s.get("tags") or {}).get("rotate", 0) or 0
                )) if (s.get("tags") or {}).get("rotate") else None,
            }
            info["video"] = v
            info["streams"].append({"type": "video", **v})
        elif s.get("codec_type") == "audio":
            info["audio_streams"] += 1
            info["streams"].append({
                "type": "audio",
                "codec": s.get("codec_name"),
                "sample_rate": s.get("sample_rate"),
                "channels": s.get("channels"),
            })

    if info["video"]:
        w, h = info["video"]["width"], info["video"]["height"]
        info["aspect_ratio"] = round(w / h, 4) if h else None
        info["orientation"] = (
            "portrait" if h > w else "landscape" if w > h else "square"
        )
        # TikTok Reels 9:16 tolerance band
        ar = info["aspect_ratio"] or 0
        info["is_9_16"] = abs(ar - 0.5625) < 0.02
    return info


# ---------------------------------------------------------------- pass 2
_SCDET = re.compile(r"lavfi\.scd\.score:\s*([0-9.]+)")
_SCDET_TIME = re.compile(r"lavfi\.scd\.time:\s*([0-9.]+)")


def scene_scores(path):
    """Per-frame scene-change score with exact timestamps.

    NOTE: `scdet` logs its own metadata straight to stderr. Adding a
    `metadata=mode=print` filter after it SILENCES those lines — you get zero
    scores and a false "no cuts detected". Do not chain metadata=print here.
    """
    rc, out = run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", "scdet=s=1:t=1",   # t=1 keeps every frame in the log
        "-f", "null", "-",
    ])
    pairs = []
    for line in out.splitlines():
        ms = _SCDET.search(line)
        if not ms:
            continue
        mt = _SCDET_TIME.search(line)
        try:
            score = round(float(ms.group(1)), 4)
            t = round(float(mt.group(1)), 3) if mt else None
        except ValueError:
            continue
        pairs.append({"t": t, "score": score})
    return pairs


# ---------------------------------------------------------------- pass 3
def black_intervals(path, min_dur=0.3, pic_th=0.98):
    rc, out = run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", f"blackdetect=d={min_dur}:pix_th=0.10:pic_th={pic_th}",
        "-f", "null", "-",
    ])
    hits = []
    for m in re.finditer(
        r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)\s+black_duration:\s*([\d.]+)",
        out,
    ):
        hits.append({
            "start": round(float(m.group(1)), 3),
            "end": round(float(m.group(2)), 3),
            "duration": round(float(m.group(3)), 3),
        })
    return hits


def freeze_intervals(path, noise_db=-60, min_dur=0.4):
    rc, out = run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", f"freezedetect=n={noise_db}dB:d={min_dur}",
        "-f", "null", "-",
    ])
    starts = [float(x) for x in re.findall(r"freeze_start:\s*([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"freeze_end:\s*([\d.]+)", out)]
    durs = [float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", out)]
    return [
        {"start": round(s, 3),
         "end": round(ends[i], 3) if i < len(ends) else None,
         "duration": round(durs[i], 3) if i < len(durs) else None}
        for i, s in enumerate(starts)
    ]


# ---------------------------------------------------------------- pass 4
_YAVG = re.compile(r"lavfi\.signalstats\.YAVG=([\d.]+)")
_SATMAX = re.compile(r"lavfi\.signalstats\.SATMAX=([\d.]+)")
_YMIN = re.compile(r"lavfi\.signalstats\.YMIN=([\d.]+)")
_YMAX = re.compile(r"lavfi\.signalstats\.YMAX=([\d.]+)")


def luma_stats(path, fps_sample=2):
    """Luma + saturation per sampled frame — cheap brightness/clipping audit.

    Each frame emits its stats in order YMIN,YLOW,YAVG,YHIGH,YMAX on separate
    lines. We start a NEW frame record on YMIN and close it on YMAX; closing on
    any later key mixes values across frames and reports garbage clipping counts.
    """
    rc, out = run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", f"fps={fps_sample},signalstats,metadata=mode=print",
        "-f", "null", "-",
    ])
    frames, cur = [], None
    for line in out.splitlines():
        m = _YMIN.search(line)
        if m:
            if cur:
                frames.append(cur)
            cur = {"y_min": float(m.group(1))}
            continue
        if cur is None:
            continue
        for rx, name in ((_YAVG, "y_avg"), (_SATMAX, "sat_max"), (_YMAX, "y_max")):
            m = rx.search(line)
            if m:
                cur[name] = float(m.group(1))
    if cur:
        frames.append(cur)
    frames = [f for f in frames if "y_max" in f and "y_avg" in f]

    if not frames:
        return {"samples": 0}
    ya = [f["y_avg"] for f in frames]
    sm = [f["sat_max"] for f in frames if "sat_max" in f]
    ymn = [f["y_min"] for f in frames if "y_min" in f]
    ymx = [f["y_max"] for f in frames if "y_max" in f]
    return {
        "samples": len(frames),
        "y_avg_mean": round(sum(ya) / len(ya), 2),
        "y_avg_min": round(min(ya), 2),
        "y_avg_max": round(max(ya), 2),
        "sat_max_mean": round(sum(sm) / len(sm), 2) if sm else None,
        # a frame is "crushed" only if its own floor AND mean are both near-black
        "crushed_black_frames": sum(1 for f in frames
                                    if f.get("y_min", 255) <= 16 and f["y_avg"] < 32),
        # blown only if its own ceiling AND mean are both near-white
        "blown_white_frames": sum(1 for f in frames
                                  if f.get("y_max", 0) >= 235 and f["y_avg"] > 210),
        "dark_frames": sum(1 for f in frames if f["y_avg"] < 40),
    }


# ---------------------------------------------------------------- verdict
def verdict(clips, scenes, blacks, freezes, luma):
    """Flags that change what you do, not just describe the file."""
    flags = []
    if clips.get("audio_streams") == 0:
        flags.append("SILENT — no audio stream; add music/sound in-app")
    if clips.get("duration_s", 0) < 5:
        flags.append(f"SHORT — {clips['duration_s']:.1f}s; below the 5-10s reach floor")
    if blacks:
        worst = max(blacks, key=lambda b: b["duration"])
        if worst["duration"] >= 0.5:
            flags.append(
                f"BLACK — {worst['duration']:.1f}s at {worst['start']:.1f}s; trim or it reads as a stall"
            )
    if freezes:
        worst = max(freezes, key=lambda f: f["duration"] or 0)
        if (worst["duration"] or 0) >= 1.5:
            flags.append(
                f"FROZEN — {(worst['duration'] or 0):.1f}s at {worst['start']:.1f}s; viewers read this as buffering"
            )
    if luma.get("dark_frames", 0) > luma.get("samples", 1) * 0.3:
        flags.append(
            f"DARK — {luma['dark_frames']}/{luma['samples']} sampled frames under luma 40"
        )
    if luma.get("y_avg_mean") is not None and luma["y_avg_mean"] > 200:
        flags.append("OVEREXPOSED — mean luma {:.0f}/255".format(luma["y_avg_mean"]))
    if not clips.get("is_9_16") and clips.get("video"):
        flags.append(
            f"ASPECT — {clips['video']['width']}x{clips['video']['height']} "
            f"({clips.get('orientation')}); needs 9:16 crop for Shorts/TikTok/Reels"
        )
    # resolution is independent of aspect: 576x1024 is a valid 9:16 but still
    # an upscale on a 1080x1920 timeline, and upscaled footage looks soft next
    # to native clips in the same feed.
    vv = clips.get("video") or {}
    if vv.get("width") and vv.get("height"):
        short_side = min(vv["width"], vv["height"])
        if short_side < 720:
            flags.append(
                f"LOW-RES — {vv['width']}x{vv['height']}; upscaling to 1080x1920 "
                f"will look soft (short side {short_side} < 720)"
            )
        elif short_side < 1080:
            flags.append(
                f"SUB-HD — {vv['width']}x{vv['height']}; usable but below the "
                f"1080x1920 native standard, mild softness when upscaled"
            )
    return flags


def main():
    if len(sys.argv) < 2:
        print("usage: vd_probe.py FILE [--json]", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.exists():
        print(json.dumps({"error": f"not found: {path}"}))
        sys.exit(1)

    clips = probe_container(path)
    if clips.get("error"):
        print(json.dumps(clips))
        sys.exit(1)

    scenes = scene_scores(path)
    blacks = black_intervals(path)
    freezes = freeze_intervals(path)
    luma = luma_stats(path)

    # top scene cuts = candidate segment boundaries
    cuts = []
    if scenes:
        thr = 12.0  # scdet is 0-100; ~12+ is a visible transition
        for s in scenes:
            if s["score"] >= thr and s["t"] is not None:
                cuts.append({"time": s["t"], "score": s["score"]})
        cuts.sort(key=lambda c: -c["score"])
    scores = [s["score"] for s in scenes]

    result = {
        "clips": clips,
        "scene": {
            "frames_scored": len(scenes),
            "max_score": max(scores) if scores else 0,
            "mean_score": round(sum(scores) / len(scores), 3) if scores else 0,
            "cuts_detected": len(cuts),
            "top_cuts": cuts[:12],
        },
        "black": blacks,
        "freeze": freezes,
        "luma": luma,
    }
    result["flags"] = verdict(clips, scenes, blacks, freezes, luma)

    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        c, v = result["clips"], result["clips"]["video"] or {}
        print(f"{c['file']}")
        print(f"  {c['duration_s']:.2f}s @ {v.get('fps')}fps  "
              f"{v.get('width')}x{v.get('height')} ({c.get('orientation')})  "
              f"{c['size_mb']} MB  {v.get('codec')}")
        print(f"  audio streams: {c['audio_streams']}   "
              f"scene cuts: {result['scene']['cuts_detected']}")
        if result["black"]:
            print(f"  black: {len(result['black'])} interval(s)")
        if result["freeze"]:
            print(f"  freeze: {len(result['freeze'])} interval(s)")
        if result["flags"]:
            print("  FLAGS:")
            for f in result["flags"]:
                print(f"    ! {f}")
        else:
            print("  FLAGS: none")


if __name__ == "__main__":
    main()
