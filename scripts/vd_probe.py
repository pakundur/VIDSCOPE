#!/usr/bin/env python3
"""
vd_probe.py — forensic probe of a video file. Emits JSON.

Pass 1  container/stream facts (ffprobe)
Pass 2  scene-change scores per frame (ffmpeg scdet)
Pass 3  black / freeze intervals (ffmpeg blackdetect, freezedetect)
Pass 4  per-frame luma + saturation (ffmpeg signalstats)

Usage:  python3 vidscope.py probe FILE [--json]
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
def _read_rotation(stream):
    """Return the display rotation in degrees, or None.

    ffmpeg 8 (and modern ffprobe generally) no longer populates `tags.rotate`;
    the rotation lives in the display matrix side data as `rotation` (degrees,
    counter-clockwise). Older files may still carry the tag. Check both, side
    data first, because that is what a player actually applies.
    """
    for sd in stream.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                return int(float(sd["rotation"]))
            except (TypeError, ValueError):
                pass
    tag = (stream.get("tags") or {}).get("rotate")
    if tag is not None:
        try:
            return int(float(tag))
        except (TypeError, ValueError):
            pass
    return None


def display_dims(v):
    """(width, height) as a player will show them, honouring rotation.

    A 720x1280 stream tagged 90/270 is *displayed* 1280x720. Every orientation,
    aspect and resolution decision must use these values, not the stored ones,
    or a landscape video in a portrait container is silently treated as 9:16.
    """
    w, h = v.get("width") or 0, v.get("height") or 0
    rot = abs(v.get("rotation") or 0) % 180
    if rot == 90:
        return h, w
    return w, h


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
                "rotation": _read_rotation(s),
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
        dw, dh = display_dims(info["video"])
        info["display_width"], info["display_height"] = dw, dh
        info["aspect_ratio"] = round(dw / dh, 4) if dh else None
        info["orientation"] = (
            "portrait" if dh > dw else "landscape" if dw > dh else "square"
        )
        # TikTok Reels 9:16 tolerance band, on DISPLAY dims
        ar = info["aspect_ratio"] or 0
        info["is_9_16"] = abs(ar - 0.5625) < 0.02
    return info


# ---------------------------------------------------------------- pass 2
_SCDET = re.compile(r"lavfi\.scd\.score=\s*([0-9.]+)")
_SCDET_TIME = re.compile(r"lavfi\.scd\.time=\s*([0-9.]+)")


def scene_scores(path):
    """Per-frame scene-change score with exact timestamps.

    `scdet` takes two thresholds and BOTH drop frames from the log:

        s  scene score floor (0-100). Frames scoring below it are not logged.
        t  scene time floor (seconds). Each frame's score is accumulated over
           this window before comparison.

    So `scdet=s=1:t=1` logs only frames scoring above 1/100. On a
    low-motion clip that is a handful of frames out of hundreds: measured
    on a 301-frame stock clip, 2 frames survived. `frames_scored` and
    `mean_score` are derived from this list, so using s=1 made both fields
    report the surviving tail rather than the clip (mean 5.348 reported
    against a true per-frame mean of 0.211, a 25x overstatement).

    `s=0` keeps every frame. `t=0` sets the accumulation window to a single
    frame, which is the per-frame score, not a coarser one.

    NOTE: `scdet` logs its own metadata straight to stderr, but chaining
    `metadata=mode=print` after it does NOT silence those lines: it emits the
    `lavfi.scd.score` value a second time in `key=value` form. The first
    regex above therefore matches `score=` (the metadata copy) and the older
    `score:` (scdet's native line) is left alone, so each frame is counted
    once only if exactly one form is parsed. Verified on a 301-frame file:
    301 rows, not 602.
    """
    rc, out = run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", "scdet=s=0:t=0,metadata=mode=print",
        "-f", "null", "-",
    ])
    # `metadata=mode=print` emits each frame as its own BLOCK of lines:
    #
    #     [Parsed_metadata_1 @ ...] frame:1  pts:512  pts_time:0.0333333
    #     [Parsed_metadata_1 @ ...] lavfi.scd.mafd=2.029
    #     [Parsed_metadata_1 @ ...] lavfi.scd.score=2.029
    #     [Parsed_metadata_1 @ ...] lavfi.scd.time=0.0333333
    #
    # and `scdet`'s own native line for the NEXT frame appears interleaved
    # between blocks. So score and time are never on one line and a
    # line-at-a-time parse yields (score, None) for every frame, which drops
    # every cut because the cut loop requires a timestamp. Parse whole blocks
    # keyed on the `pts_time` frame header instead.
    pairs = []
    score = None
    prev_t = 0.0
    for line in out.splitlines():
        mt = re.search(r"pts_time:([0-9.]+)", line)
        if mt:
            # a new frame header: flush the previous block
            if score is not None:
                pairs.append({"t": prev_t, "score": score})
            prev_t = round(float(mt.group(1)), 3)
            score = None
            continue
        ms = _SCDET.search(line)
        if ms:
            try:
                score = round(float(ms.group(1)), 4)
            except ValueError:
                score = None
    if score is not None:
        pairs.append({"t": prev_t, "score": score})
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


def freeze_intervals(path, noise_db=-60, min_dur=0.4, duration=None):
    """Frozen-frame intervals.

    ffmpeg only emits `freeze_end` / `freeze_duration` when the freeze actually
    ends before EOF. A clip that is frozen *at the end* — the worst case, since
    it reads as a hang — logs `freeze_start` alone and nothing else. Parsing
    starts/ends as parallel arrays silently drops those, so a 3-second still
    frame passed as clean. Track open intervals instead and close any that are
    still open at EOF using the clip duration.
    """
    rc, out = run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", f"freezedetect=n={noise_db}dB:d={min_dur}",
        "-f", "null", "-",
    ])
    hits = []
    open_start = None
    for line in out.splitlines():
        m = re.search(r"freeze_start:\s*([\d.]+)", line)
        if m:
            open_start = float(m.group(1))
            continue
        m = re.search(r"freeze_duration:\s*([\d.]+)", line)
        if m and open_start is not None:
            dur = float(m.group(1))
            hits.append({"start": round(open_start, 3),
                         "end": round(open_start + dur, 3),
                         "duration": round(dur, 3),
                         "runs_to_eof": False})
            continue
        m = re.search(r"freeze_end:\s*([\d.]+)", line)
        if m and open_start is not None:
            end = float(m.group(1))
            # freeze_duration usually already closed this; avoid duplicates
            if not hits or hits[-1]["start"] != round(open_start, 3):
                hits.append({"start": round(open_start, 3),
                             "end": round(end, 3),
                             "duration": round(end - open_start, 3),
                             "runs_to_eof": False})
            open_start = None

    # freeze still open at EOF -> it never ended
    if open_start is not None:
        end = duration if duration else None
        dur = (end - open_start) if end else None
        hits.append({"start": round(open_start, 3),
                     "end": round(end, 3) if end else None,
                     "duration": round(dur, 3) if dur else None,
                     "runs_to_eof": True})
    return hits


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
        # A frame is "crushed" when its own floor is at or below the 16 code
        # value AND its mean is near-black. Testing y_min <= 16 alone is
        # useless: pure black sits at exactly 16, and so does every frame with
        # one dark corner. Both conditions must hold.
        "crushed_black_frames": sum(1 for f in frames
                                    if f.get("y_min", 255) <= 17 and f["y_avg"] < 32),
        # blown only if its own ceiling AND mean are both near-white
        "blown_white_frames": sum(1 for f in frames
                                  if f.get("y_max", 0) >= 235 and f["y_avg"] > 210),
        "dark_frames": sum(1 for f in frames if f["y_avg"] < 40),
    }


# ---------------------------------------------------------------- verdict
def verdict(clips, scenes, blacks, freezes, luma):
    """Flags that change what you do, not just describe the file."""
    flags = []
    if not clips.get("video"):
        # An audio-only file is not "short" first, it has no picture. Naming the
        # wrong problem is worse than saying nothing: a caller was previously
        # told SHORT when the real answer was that there is nothing to look at.
        flags.append("NO-VIDEO — no video stream; audio-only file")
    if clips.get("audio_streams") == 0:
        flags.append("SILENT — no audio stream; add music/sound in-app")
    if clips.get("duration_s", 0) < 5 and clips.get("video"):
        flags.append(f"SHORT — {clips['duration_s']:.1f}s; below the 5-10s reach floor")
    if blacks:
        worst = max(blacks, key=lambda b: b["duration"])
        if worst["duration"] >= 0.5:
            flags.append(
                f"BLACK — {worst['duration']:.1f}s at {worst['start']:.1f}s; trim or it reads as a stall"
            )
    if freezes:
        worst = max(freezes, key=lambda f: (f["duration"] or 0))
        wd = worst.get("duration")
        if wd is None and worst.get("runs_to_eof"):
            # freeze to EOF with unknown length -> it is the tail of the clip
            flags.append(
                f"FROZEN — from {worst['start']:.1f}s to end of clip; the video "
                f"stops moving before it stops playing"
            )
        elif (wd or 0) >= 1.5:
            flags.append(
                f"FROZEN — {wd:.1f}s at {worst['start']:.1f}s; viewers read this as buffering"
            )
    if luma.get("dark_frames", 0) > luma.get("samples", 1) * 0.3:
        flags.append(
            f"DARK — {luma['dark_frames']}/{luma['samples']} sampled frames under luma 40"
        )
    if luma.get("y_avg_mean") is not None and luma["y_avg_mean"] > 200:
        flags.append("OVEREXPOSED — mean luma {:.0f}/255".format(luma["y_avg_mean"]))
    if not clips.get("is_9_16") and clips.get("video"):
        dw = clips.get("display_width") or clips["video"]["width"]
        dh = clips.get("display_height") or clips["video"]["height"]
        rot = clips["video"].get("rotation")
        note = ""
        if rot:
            sw, sh = clips["video"]["width"], clips["video"]["height"]
            note = f" [stored {sw}x{sh}, rotation {rot}°]"
        flags.append(
            f"ASPECT — {dw}x{dh} displayed ({clips.get('orientation')}){note}; "
            f"needs 9:16 crop for Shorts/TikTok/Reels"
        )
    # resolution is independent of aspect: 576x1024 is a valid 9:16 but still
    # an upscale on a 1080x1920 timeline, and upscaled footage looks soft next
    # to native clips in the same feed. Judge on DISPLAY dims, so a rotated
    # landscape clip is not credited with portrait resolution.
    vv = clips.get("video") or {}
    dw = clips.get("display_width") or vv.get("width")
    dh = clips.get("display_height") or vv.get("height")
    if dw and dh:
        short_side = min(dw, dh)
        if short_side < 720:
            flags.append(
                f"LOW-RES — {dw}x{dh}; upscaling to 1080x1920 will look soft "
                f"(short side {short_side} < 720)"
            )
        elif short_side < 1080:
            flags.append(
                f"SUB-HD — {dw}x{dh}; usable but below the 1080x1920 native "
                f"standard, mild softness when upscaled"
            )
    return flags


def main():
    if len(sys.argv) < 2:
        print("usage: vidscope probe FILE [--json]", file=sys.stderr)
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
    freezes = freeze_intervals(path, duration=clips.get("duration_s"))
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

    # Pacing. A count of cuts says little on its own: 8 cuts in 10s and 8 cuts in
    # 30s are different videos. Shot length and cut rate are what a caller can
    # actually compare between clips, and mean_score separates a static shot
    # from a busy one on its own (measured range across 20 stock clips: 0.21 to
    # 0.92, while every clip that was a single take sat under 0.35).
    dur = clips.get("duration_s") or 0
    try:
        dur = float(dur)
    except (TypeError, ValueError):
        dur = 0.0
    if dur > 0 and clips.get("video"):
        times = sorted(c["time"] for c in cuts)
        shots = [b - a for a, b in zip([0.0] + times, times + [dur])]
        shots = [s for s in shots if s > 0]
        result["scene"]["cuts_per_minute"] = round(len(cuts) * 60.0 / dur, 1)
        result["scene"]["shot_length_median_s"] = (
            round(sorted(shots)[len(shots) // 2], 2) if shots else None
        )
    result["flags"] = verdict(clips, scenes, blacks, freezes, luma)

    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        c, v = result["clips"], result["clips"]["video"] or {}
        dw = c.get("display_width") or v.get("width")
        dh = c.get("display_height") or v.get("height")
        rot = v.get("rotation")
        # print DISPLAY dimensions with the display orientation -- printing
        # stored 720x1280 next to "(landscape)" reads as a contradiction
        dims = f"{dw}x{dh}"
        if rot:
            dims += f" (stored {v.get('width')}x{v.get('height')}, rotated {rot}°)"
        print(f"{c['file']}")
        print(f"  {c['duration_s']:.2f}s @ {v.get('fps')}fps  "
              f"{dims} ({c.get('orientation')})  "
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
