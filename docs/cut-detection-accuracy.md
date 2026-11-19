# Cut detection: recall and precision, measured

Two questions, two answers. Both were measured on real footage, not fixtures.

## Precision: every reported cut is real

91 reported cuts across 20 real stock clips, scored against per-frame
scene-difference data. 91/91 landed on a genuine frame-to-frame
discontinuity. Zero false positives.

Caveat on method: the first time this was measured it read 79.1%, and
that number was wrong. These clips are edited montages with cuts every
1-3 seconds, so each clip's 99th-percentile score sits inside the cut
population and a real cut can fall below it. Re-scoring against an
adaptive threshold (8x the clip median) gave 100% and individual
inspection confirmed it.

## Recall: 30/30 on constructed cuts

Recall cannot be measured against footage whose cut list you guessed.
It has to be constructed. Method:

1. Mine single-shot segments out of the corpus. A segment sitting
   strictly between two known cuts is continuous by construction.
   Yields 713s of verified single-shot material across 64 clips.
2. Concatenate N segments. The result has exactly N-1 cuts, at the
   cumulative durations. Ground truth is arithmetic.
3. Ask VidScope where it thinks the cuts are; a true cut counts as found
   if a reported cut lands within 0.30s.

Result: 30 constructed cuts across 15 spliced clips (2, 3 and 4 segment
builds), **30 found, 0 missed, 0 false positives**.

## The one apparent miss, and why it was not the tool

A first run reported 91.7% with two misses. Both traced to the test, not
the code:

- The harness normalised segments with `scale`+`pad`+`-r 30`, which
  produced a duplicated frame at the splice point on some builds.
- `scdet` computes its score from the difference between consecutive
  frames. When a cut is immediately followed by a byte-identical
  duplicate, the frame at the boundary compares equal to its
  successor, so `scdet` reports 0.000 for a cut the eye sees plainly.
  Measured directly: frame 119 to 120 differs by 67.4 grey levels (the
  real cut) while 120 to 121 differs by 0.0 (the duplicate), and the
  reported score at that boundary was 0.000.

This is a real ffmpeg behaviour worth knowing, not a VidScope defect,
but it does mean a cut adjacent to a duplicated frame can be
under-reported. It only occurred in spliced material here; none of the
20 real clips contained duplicate frames.

## What is still not proven

- All footage is short portrait social video, 720x1280 or 576x1024.
  Nothing here covers 4K, HDR, 10-bit, VFR or long-form.
- Recall was measured on hard cuts between visually distinct shots.
  Dissolves, wipes and fades are not represented and `scdet` is not
  designed to find them.
- No clip in the corpus or the splice set followed a cut with a
  duplicated frame, except by accident in the splice harness, so the
  under-reporting above is characterised but not quantified.

## Reproducing

    python3 tests/mine_segments.py     # build single-shot segment pool
    python3 tests/recall_spliced.py    # construct cuts, measure recall

Both take a directory of real clips and write their results to JSON.
They are not wired into the unit suite because they need a video corpus
and take minutes to run.
