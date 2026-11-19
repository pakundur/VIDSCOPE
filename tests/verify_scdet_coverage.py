"""Re-measure with FULL per-frame scdet data (scdet=t=0), not just above-threshold frames."""
import subprocess, re, os, statistics
os.chdir('/data/data/com.termux/files/home/folders/work4/stock')

def full_scores(f):
    e = subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',f,'-vf',
        'scdet=t=0,metadata=mode=print','-f','null','-'],
        capture_output=True, text=True).stderr
    # take only the metadata=print lines (dedup: scdet's own line has ", lavfi.scd.time:")
    rows = re.findall(r'pts_time:([\d.]+)[^\n]*\n\[[^\]]+\] lavfi\.scd\.score=([\d.]+)', e)
    if not rows:
        # fallback: scdet's native lines
        rows = [(t, s) for s, t in re.findall(
            r'lavfi\.scd\.score: ([\d.]+), lavfi\.scd\.time: ([\d.]+)', e)]
    return [(float(t), float(s)) for t, s in rows]

print(f"{'clip':<14}{'frames':>7}{'median':>8}{'p90':>7}{'p99':>7}{'max':>7}{'>12':>5}{'>6':>5}")
for c in ['HOME-A2-450','HOME-B1-174','HOME-B1-307','HOME-A1-195','HOME-A1-007',
          'HOME-B1-186','HOME-A2-603','HOME-A1-179','HOME-B1-103','HOME-A1-198']:
    ss = full_scores(c + '.mp4')
    if not ss:
        print(f"{c}: no data"); continue
    v = sorted(s for _, s in ss)
    med = statistics.median(v)
    print(f"{c:<14}{len(v):>7}{med:>8.3f}{v[int(len(v)*.90)]:>7.1f}"
          f"{v[int(len(v)*.99)]:>7.1f}{v[-1]:>7.1f}"
          f"{sum(1 for x in v if x>=12):>5}{sum(1 for x in v if x>=6):>5}")
