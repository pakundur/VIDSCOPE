#!/usr/bin/env python3
"""Score VidScope's black/freeze claims against independent ffmpeg ground truth."""
import json, glob, subprocess, os, re

os.chdir(os.environ.get('VS_STOCK', os.path.join('..', 'work4', 'stock')))

def run(args):
    return subprocess.run(args, capture_output=True, text=True).stderr

def truth(f):
    r = {}
    # blackdetect with a STRICT pixel threshold (pix_th=0.10) so a bright
    # title card cannot be mistaken for a black interval.
    e = run(['ffmpeg','-hide_banner','-nostats','-i',f,
        '-vf','blackdetect=d=0.20:pic_th=0.98:pix_th=0.10','-an','-f','null','-'])
    r['black'] = [(float(a),float(b)) for a,b in
                  re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', e)]
    e = run(['ffmpeg','-hide_banner','-nostats','-i',f,
        '-vf','freezedetect=n=0.003:d=1.0','-an','-f','null','-'])
    starts=[float(x) for x in re.findall(r'freeze_start: ([\d.]+)', e)]
    ends=[float(x) for x in re.findall(r'freeze_end: ([\d.]+)', e)]
    r['freeze'] = list(zip(starts, ends))
    e = run(['ffmpeg','-hide_banner','-nostats','-i',f,
        '-vf','signalstats,metadata=print','-an','-f','null','-'])
    yav=[float(x) for x in re.findall(r'lavfi.signalstats.YAVG=([\d.]+)', e)]
    yhi=[float(x) for x in re.findall(r'lavfi.signalstats.YHIGH=([\d.]+)', e)]
    r['yavg_mean']=round(sum(yav)/len(yav),2) if yav else None
    r['yhigh_mean']=round(sum(yhi)/len(yhi),2) if yhi else None
    return r

rows=[]
for jf in sorted(glob.glob('out/*.json')):
    try: d=json.load(open(jf))
    except Exception: continue
    f=d['clips']['file']
    t=truth(f)
    rows.append(dict(clip=f.replace('.mp4',''), dur=d['clips']['duration_s'],
        vb=len(d.get('black') or []), tb=len(t['black']),
        vf=len(d.get('freeze') or []), tf=len(t['freeze']),
        vy=d['luma']['y_avg_mean'], ty=t['yavg_mean'], yh=t['yhigh_mean'],
        flags=d.get('flags') or [], cuts=d['scene']['cuts_detected'],
        ms=d['scene']['max_score'],
        raw_black=d.get('black') or [], raw_freeze=d.get('freeze') or []))

print(f"{'clip':<14}{'dur':>6}{'BLK vs/true':>13}{'FRZ vs/true':>13}{'yavg vs/true':>15}{'yhigh':>7}{'cuts':>6}{'maxsc':>7}  flags")
bad=[]
for r in rows:
    m=''
    if r['vb'] and not r['tb']: m+=' BLACK-FP'
    if r['vf'] and not r['tf']: m+=' FREEZE-FP'
    if r['vb']!=r['tb'] or r['vf']!=r['tf']: bad.append((r['clip'],m or ' COUNT-DIFF'))
    print(f"{r['clip']:<14}{r['dur']:>6.1f}{r['vb']:>6}/{r['tb']:<6}{r['vf']:>6}/{r['tf']:<6}"
          f"{r['vy']:>7}/{r['ty']:<7}{r['yh']:>7.1f}{r['cuts']:>6}{r['ms']:>7.1f}  {','.join(r['flags'])}{m}")

print(f"\nMISMATCHES: {len(bad)} / {len(rows)}")
for c,m in bad:
    print('  ',c,m)
    for r in rows:
        if r['clip']==c:
            if r['raw_black']: print('      vs black :',r['raw_black'])
            if r['raw_freeze']: print('      vs freeze:',r['raw_freeze'])
