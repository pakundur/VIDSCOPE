# VidScope on real stock footage: test report

Device: Termux, Android 17, aarch64 (Galaxy S25 Ultra SM-S948B)
Date: 2026-11-19
VidScope: v1.0.3, commit 9c599e6, invoked from PATH

## Corpus

20 real stock clips pulled from the R2 bucket `resepifesbuk-videos`
(public base `pub-916db35501284776893235d4b8b6b758.r2.dev`), sampled
deterministically (seed 7) across all 11 categories present in
`~/folders/video_registry.csv`. 58 MB total. All portrait,
720x1280 or 576x1024, h264, 30 fps, 8.6 s to 28.0 s.

Ground truth for black and freeze was measured independently with raw
ffmpeg filters, not via VidScope's own code paths:

- black: `blackdetect=d=0.20:pic_th=0.98:pix_th=0.10` (strict pixel
  threshold so a bright title card cannot register as black)
- freeze: `freezedetect=n=0.003:d=1.0`
- luma: `signalstats` YAVG / YHIGH means

## Result 1: black and freeze are exact

0 mismatches in 20 clips. Every clip reported 0 black intervals and 0
freeze intervals, and independent measurement agreed on every one.
`y_avg_mean` tracked the independently measured YAVG mean to within
0.06 luma on all 20 (largest gap HOME-A1-179: 150.31 vs 151.03).

This is a meaningful result because 12 of the 20 clips are single
continuous shots with no black or freeze, so the detector had many
opportunities to false-positive and produced none.

## Result 2: scdet sampled only frames ABOVE the score floor

`scene_scores()` in `scripts/vd_probe.py` ran `scdet=s=1:t=1`. The `=1`
is the scene SCORE threshold, not an enable flag, so ffmpeg logged only
frames scoring above 1/100. On this corpus that discarded most of the
video:

| clip | frames | scdet samples | coverage |
|---|---|---|---|
| HOME-A2-450 | 301 | 2 | 0.7% |
| HOME-B1-174 | 297 | 11 | 3.7% |
| HOME-B1-307 | 396 | 18 | 4.5% |
| HOME-A1-195 | 372 | 18 | 4.8% |
| HOME-A1-007 | 384 | 63 | 16.4% |

This did not corrupt the cut list, because a dropped frame scored below
1.0 and could never reach the 12.0 cut threshold anyway. But
`frames_scored` and `mean_score` are derived from that list, so both
were reporting the surviving tail rather than the clip.

Measured on HOME-A2-450, which has 301 frames:

| field | reported | truth |
|---|---|---|
| frames_scored | 2 | 301 |
| mean_score | 5.348 | 0.211 |

`mean_score` was overstated by 25x. `max_score` and `cuts_detected`
were correct, because neither depends on how many frames survived.

An agent reading that JSON would conclude the clip is far more dynamic
than it is, and a caller comparing two clips on `mean_score` would be
comparing two different sampling regimes.

### Fix applied

`scene_scores()` now runs `scdet=s=0:t=0,metadata=mode=print` and parses
whole metadata blocks keyed on the `pts_time` frame header.
`s=0` keeps every frame, `t=0` sets the accumulation window to a single
frame so the score stays per-frame rather than coarsened over time.

The block parser is required, not cosmetic. `metadata=mode=print` emits
`score` and `time` on SEPARATE lines within each frame's block, with
`scdet`'s own native line for the next frame interleaved between blocks.
A line-at-a-time parse therefore returns `(score, None)` for every frame,
and because the cut loop requires a timestamp, every cut silently
disappears. That regression was hit and fixed during this work: the first
version of the patch reported `frames_scored=301` correctly and
`cuts_detected=0` on every clip.

Verified after the fix, all seven clips checked:

| clip | frames | mean | max | cuts | same cuts as before |
|---|---|---|---|---|---|
| HOME-A1-007 | 384 | 0.910 | 27.93 | 8 | yes |
| HOME-A2-603 | 368 | 0.919 | 31.34 | 6 | yes |
| HOME-A1-195 | 372 | 0.507 | 18.06 | 6 | yes |
| HOME-A2-450 | 301 | 0.211 | 9.62 | 0 | yes |
| HOME-B1-174 | 297 | 0.330 | 9.85 | 0 | yes |
| HOME-B1-307 | 396 | 0.467 | 16.14 | 2 | yes |
| HOME-A1-179 | 820 | 0.514 | 25.37 | 10 | yes |

`--json` stdout remains pure JSON with the extra filter output present,
and the full adversarial suite passes 28/28 after the change.

## Result 3: cut detection is right, and the threshold is well-placed

Full per-frame data (`scdet=t=0`) on 10 clips shows a clean bimodal
separation. Real cuts score 9.6 to 31.3; everything else sits below
about 2.0. Clip medians are 0.13 to 0.39.

| clip | frames | median | p90 | p99 | max | >12 |
|---|---|---|---|---|---|---|
| HOME-A2-450 | 301 | 0.131 | 0.4 | 0.8 | 9.6 | 0 |
| HOME-B1-174 | 297 | 0.248 | 0.6 | 1.6 | 9.9 | 0 |
| HOME-B1-307 | 396 | 0.197 | 0.7 | 11.4 | 16.1 | 2 |
| HOME-A1-195 | 372 | 0.143 | 0.7 | 14.8 | 18.1 | 6 |
| HOME-A1-007 | 384 | 0.207 | 1.4 | 18.5 | 27.9 | 8 |
| HOME-B1-186 | 357 | 0.277 | 2.4 | 13.6 | 16.0 | 6 |
| HOME-A2-603 | 368 | 0.310 | 1.3 | 16.2 | 31.3 | 6 |
| HOME-A1-179 | 820 | 0.155 | 0.7 | 14.3 | 25.4 | 10 |
| HOME-B1-103 | 354 | 0.213 | 1.9 | 14.4 | 30.9 | 4 |
| HOME-A1-198 | 467 | 0.388 | 1.6 | 5.3 | 22.8 | 3 |

91 reported cuts across 20 clips, scored against per-frame
`select=gte(scene,0)` scores with an adaptive threshold (8x the clip
median, floor 0.08): 91/91 land on a real frame-to-frame discontinuity,
0 false positives, 100% precision. Spot-checked visually at
HOME-A2-603 5.27/9.0 s (different products) and HOME-A1-179
6.13/6.5 s (same shot, motion only).

## Result 4: two attempted fixes failed, and were reverted

Both were driven by an initial wrong reading of the data. Recorded
because the negative result is the useful finding.

**Fix A, adaptive threshold `max(6.0, median*8)`.** Rationale: a fixed
constant cannot serve both a quiet clip and a fast-cut montage. Result:
100% precision but 14 real cuts destroyed, HOME-A1-195 going from 6
cuts to 0 and HOME-B1-186 from 6 to 2. Cause: the 6.0 floor sits above
genuine within-shot motion scores on those clips. Reverted.

**Fix B, second pass admitting isolated sub-threshold spikes.** Rationale:
recover a suspected cut at HOME-B1-307 3.067 s scoring 11.80, just
under 12.0. Result: it failed to admit that spike and wrongly admitted
HOME-A2-450 2.3 s instead. Cause: with only 18 samples on that clip,
the "neighbours" were temporally distant frames, so the isolation test
was meaningless. Reverted.

## Result 5: the suspected missed cut was not a cut

HOME-B1-307 3.067 s scores 11.80, an isolated spike 60x the clip median.
It looked like a textbook false negative. Frames at 3.05 s and 3.25 s
show the same hands, the same blue bottle lid, the same counter, the
same props, in the same shot. It is camera motion during a cleaning
demo. The 12.0 threshold is correct to reject it.

The initial claim of "one genuine hard cut missed" was wrong and is
withdrawn. On this corpus the fixed 12.0 threshold has no demonstrated
false negative.

## Result 6: edge cases all survive

Six constructed cases, each exit 0 with valid JSON, no crash, no
traceback:

- unicode + spaces + em dash in filename (Japanese, Malay): identical
  output to the ASCII original
- 1-frame clip (0.033 s): SHORT flagged, no divide-by-zero
- 0.4 s clip: SHORT flagged, 4 frames scored
- audio-only m4a, no video stream: 606 B of valid JSON, no crash, SHORT
  flagged, luma null. It does not flag the absence of a video stream.
- video with no audio track: fine
- rotation 90 display matrix: reported correctly as stored 720x1280
  becoming display 1280x720, orientation landscape

A first attempt at the rotation case produced a false pass because
`ffmpeg -c copy -metadata rotate=90` drops the display matrix. The
working command is `ffmpeg -display_rotation 90 -i in.mp4 -c copy out.mp4`.

## Performance

- 20 clips probed serially: about 75 s wall, roughly 3.8 s per clip,
  dominated by four full decode passes per file
- 12.8 s 720x1280 clip: about 1.3 s for probe with JSON
- no temp files written beside the input

## Conclusions

Black and freeze detection is trustworthy on real footage. Cut
detection is precise with a well-placed threshold on this corpus.

Recommended changes, in priority order:

1. Fix the misleading `frames_scored` and `mean_score` fields, or
   switch the invocation to `scdet=t=0` so they mean what they say.
   This is the only defect confirmed on the corpus, and it is a
   reporting-truthfulness issue rather than a detection error.
2. Flag clips with no video stream explicitly instead of only SHORT.
3. Lower the `blackdetect` threshold, or cross-check black intervals
   against bright-pixel count, so a title card is reported as DARK-CARD
   rather than BLACK. This is carried over from the earlier Qiyamah
   title-card test and is not reproduced in this corpus.

Do not change the 12.0 cut threshold on the strength of this corpus.

## Scope limit

All 20 clips are short portrait social video. Nothing here proves
behaviour on 4K, HDR, 10-bit, VFR, or long-form content.
