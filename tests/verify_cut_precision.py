#!/usr/bin/env python3
"""Validate VidScope's reported cut TIMES against independent per-frame scene scores.

For each reported cut we check whether a genuine frame-to-frame discontinuity
exists near that timestamp. A cut with no discontinuity nearby is a false positive;
a large discontinuity far from any reported cut is a miss.
"""
import json, glob, subprocess, os, re, bisect

os.chdir(os.environ.get('VS_STOCK', os.path.join('..', 'work4', 'stock')))

def frame_scores(f):
    e = subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',f,'-vf',
        'select=gte(scene\\,0),metadata=print','-an','-f','null','-'],
        capture_output=True, text=True).stderr
    pts = [float(x) for x in re.findall(r'pts_time:([\d.]+)', e)]
    sc  = [float(x) for x in re.findall(r'scene_score=([\d.]+)', e)]
    return list(zip(pts, sc))

tot_cuts = tot_ok = 0
missed_all = []
rows = []
for jf in sorted(glob.glob('out/*.json')):
    d = json.load(open(jf))
    f = d['clips']['file']
    dur = d['clips']['duration_s']
    fs = frame_scores(f)
    if not fs:
        continue
    cuts = [c['time'] for c in (d['scene'].get('top_cuts') or [])]
    times = [t for t,_ in fs]
    # threshold for a "genuine" discontinuity: this clip's own p99, floored
    ss = sorted(s for _,s in fs)
    thr = max(0.05, ss[int(len(ss)*0.99)])
    # local discontinuity magnitude around a timestamp (window +-0.25s)
    def local_mag(t):
        lo = bisect.bisect_left(times, t-0.25)
        hi = bisect.bisect_right(times, t+0.25)
        return max((s for _,s in fs[lo:hi]), default=0.0)
    ok = 0
    for t in cuts:
        if local_mag(t) >= thr:
            ok += 1
    # misses: big discontinuities with no reported cut within 0.5s
    missed = []
    for t,s in fs:
        if s >= max(thr*2, 0.20):
            if not any(abs(t-c) <= 0.5 for c in cuts):
                missed.append((round(t,2), round(s,3)))
    tot_cuts += len(cuts); tot_ok += ok
    missed_all.append((f.replace('.mp4',''), missed))
    rows.append((f.replace('.mp4',''), dur, len(fs), thr, len(cuts), ok, len(missed)))

print(f"{'clip':<14}{'dur':>6}{'frames':>7}{'thr':>7}{'cuts':>6}{'real':>6}{'missed':>8}")
for r in rows:
    print(f"{r[0]:<14}{r[1]:>6.1f}{r[2]:>7}{r[3]:>7.3f}{r[4]:>6}{r[5]:>6}{r[6]:>8}")

print(f"\nCut precision: {tot_ok}/{tot_cuts} reported cuts land on a real discontinuity "
      f"({100.0*tot_ok/max(tot_cuts,1):.1f}%)")
tot_miss = sum(len(m) for _,m in missed_all)
print(f"Large discontinuities with no nearby reported cut: {tot_miss}")
for c,m in missed_all:
    if m:
        print(f"  {c}: {m[:6]}{' ...' if len(m)>6 else ''}")
