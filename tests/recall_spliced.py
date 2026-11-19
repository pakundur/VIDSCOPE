#!/usr/bin/env python3
"""Recall test, second attempt, with the corrected understanding of scdet.

Corrections that invalidate the first run's framing:
  * `t=` / `threshold=` is the SCORE threshold (default 10), not a time window.
  * `s=` is `sc_pass`, a boolean passthrough flag, irrelevant to scores.
  So `scdet=t=0` is the minimum threshold that logs every frame. The earlier
  `s=1:t=1` in the codebase was equivalent to threshold=1.

Ground truth stays arithmetic (concatenation boundaries). But a concatenation
boundary only counts as a TRUE CUT if scdet can perceive it at all. Two
segments that look alike, or that are separated by a fade or a duplicate
frame, are not perceptible cuts. So this test reports both:
  * recall against all construction boundaries (the pessimistic number)
  * whether each boundary was even perceptible (measured by frame difference,
    independent of scdet)
"""
import subprocess, re, os, json, random, hashlib

WORK='/data/data/com.termux/files/home/folders/work4'
OUT=os.path.join(WORK,'spliced')
THR=12.0
TOL=0.30

def run(a): return subprocess.run(a,capture_output=True,text=True)

def duration(f):
    p=run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',f])
    return float(p.stdout.strip())

def scores(f):
    e=run(['ffmpeg','-hide_banner','-nostats','-i',f,'-vf',
           'scdet=t=0,metadata=mode=print','-f','null','-']).stderr
    rows=[];cur=None
    for line in e.splitlines():
        m=re.search(r'pts_time:([0-9.]+)',line)
        if m: cur=float(m.group(1)); continue
        m=re.search(r'lavfi\.scd\.score=\s*([0-9.]+)',line)
        if m and cur is not None: rows.append((cur,float(m.group(1))))
    return rows

def frame_diffs(f):
    """Per-frame mean abs difference on a small grey thumbnail, independent of scdet."""
    out=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',f,
        '-vf','scale=48:86','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True).stdout
    n=48*86
    fr=[out[i:i+n] for i in range(0,len(out),n)]
    diffs=[]
    for i in range(1,len(fr)):
        a,b=fr[i-1],fr[i]
        d=sum(abs(x-y) for x,y in zip(a,b))/max(len(a),1)
        diffs.append(d)
    return diffs

def vcuts(f):
    p=run(['vidscope','probe',f,'--json'])
    try: d=json.loads(p.stdout)
    except Exception: return []
    return [round(c['time'],3) for c in d['scene']['top_cuts']]

def build(parts,out):
    lst=os.path.join(OUT,'list.txt')
    with open(lst,'w') as fh:
        for p in parts: fh.write(f"file '{p}'\n")
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',lst,'-c','copy',out])
    cuts=[];acc=0.0
    for p in parts[:-1]:
        acc+=duration(p); cuts.append(round(acc,3))
    return cuts

def norm(seg,i):
    p=os.path.join(OUT,f'seg{i}.mp4')
    run(['ffmpeg','-hide_banner','-loglevel','error','-y',
         '-ss',str(seg['t0']),'-to',str(seg['t1']),'-i',seg['src'],'-an',
         '-vf','scale=720:1280:force_original_aspect_ratio=decrease,'
         'pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1','-r','30',
         '-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',p])
    return p

segs=json.load(open(os.path.join(WORK,'segments.json')))
segs=[s for s in segs if s['dur']>=1.4]
random.seed(23); random.shuffle(segs)

rows=[]
for n in (2,3,4):
    for k in range(5):
        if len(segs)<n: break
        picked=[segs.pop() for _ in range(n)]
        parts=[norm(s,i) for i,s in enumerate(picked)]
        parts=[p for p in parts if os.path.exists(p) and duration(p)>0.4]
        if len(parts)<2: continue
        name=f'v2_{n}seg_{k}'
        out=os.path.join(OUT,name+'.mp4')
        true_cuts=build(parts,out)
        sc=scores(out); found=vcuts(out)
        diffs=frame_diffs(out)
        # perceptibility: frame-diff spike at the boundary, relative to clip median
        import statistics
        med=statistics.median(diffs) if diffs else 0
        for t in true_cuts:
            fi=int(round(t*30))
            win=diffs[max(0,fi-2):fi+2]
            peak=max(win) if win else 0
            perceptible = peak > max(med*6, 4.0)
            hit=any(abs(t-f)<=TOL for f in found)
            # what scdet itself saw
            fis=max(sc,key=lambda x:x[1])[1] if sc else 0
            near=[sg for tt,sg in sc if abs(tt-t)<=0.12]
            rows.append(dict(clip=name,true=t,hit=hit,perceptible=perceptible,
                             peak=round(peak,1),med=round(med,1),
                             scdet_max_near=round(max(near),2) if near else 0,
                             scdet_clip_max=round(fis,1)))

json.dump(rows,open(os.path.join(WORK,'recall_v2.json'),'w'),indent=1)

per=[r for r in rows if r['perceptible']]
imp=[r for r in rows if not r['perceptible']]
hit_p=sum(1 for r in per if r['hit'])
hit_i=sum(1 for r in imp if r['hit'])
print(f"{'clip':<14}{'true':>7}{'peak':>7}{'med':>6}{'percept':>9}{'scdNear':>9}{'found':>7}")
for r in rows:
    print(f"{r['clip']:<14}{r['true']:>7.2f}{r['peak']:>7.1f}{r['med']:>6.1f}"
          f"{'yes' if r['perceptible'] else 'NO':>9}{r['scdet_max_near']:>9.2f}"
          f"{'HIT' if r['hit'] else 'miss':>7}")

print(f"\n=== boundaries {len(rows)} total")
print(f"    perceptible cut-like: {len(per)}, found {hit_p} -> recall {100*hit_p/max(len(per),1):.1f}%")
print(f"    NOT perceptible (alike/faded): {len(imp)}, found {hit_i}")
print(f"    overall: found {hit_p+hit_i}/{len(rows)}")
