#!/usr/bin/env python3
"""Mine single-shot SEGMENTS out of busy clips.

Rationale: only 3 of 64 stock clips are internally cut-free, which is too
little variety for a recall test. But a busy clip contains runs of frames
between its cuts that are themselves continuous. Extracting a window that
sits strictly between two known cuts yields single-shot material by
construction, and I know its start and end exactly.

This keeps ground truth arithmetic instead of inferred.
"""
import subprocess, re, os, json

WORK='/data/data/com.termux/files/home/folders/work4'
THR=12.0
MIN_LEN=0.8   # shortest segment worth splicing

def full_scores(f):
    p=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',f,'-vf',
        'scdet=s=0:t=0,metadata=mode=print','-f','null','-'],capture_output=True,text=True)
    return [float(x) for x in re.findall(r'lavfi\.scd\.score=\s*([0-9.]+)',p.stderr)]

def fps(f):
    p=subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=r_frame_rate','-of','default=nw=1:nk=1',f],
        capture_output=True,text=True)
    n,d=p.stdout.strip().split('/')
    return float(n)/float(d)

segs=[]
for d in ['stock','stock2']:
    base=os.path.join(WORK,d)
    if not os.path.isdir(base): continue
    for f in sorted(os.listdir(base)):
        if not f.endswith('.mp4'): continue
        path=os.path.join(base,f)
        sc=full_scores(path)
        if not sc: continue
        fr=fps(path)
        # cut frames = those at/above threshold
        cut_idx=[i for i,s in enumerate(sc) if s>=THR]
        # build quiet runs between cuts
        bounds=[-1]+cut_idx+[len(sc)]
        for a,b in zip(bounds,bounds[1:]):
            start_f, end_f = a+1, b-1
            dur=(end_f-start_f+1)/fr
            if dur < MIN_LEN: continue
            # pad inward so we never touch the cut frame itself
            t0=round(start_f/fr+0.05,3)
            t1=round((end_f+1)/fr-0.05,3)
            if t1-t0 < MIN_LEN: continue
            segs.append({'src':path,'t0':t0,'t1':t1,'dur':round(t1-t0,3),
                         'clip':f.replace('.mp4','')})

print(f"mined {len(segs)} single-shot segments from {len(set(s['clip'] for s in segs))} clips")
by=json.dumps(segs[:5],indent=1)
print(by)
json.dump(segs,open(os.path.join(WORK,'segments.json'),'w'),indent=1)
print(f"\nusable segment total duration: {sum(s['dur'] for s in segs):.1f}s")
