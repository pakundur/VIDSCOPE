# Changelog

## 1.0.1 — 2026-11-17

Bug hunt pass. Four real defects found by adversarial testing, each of which
produced **silently wrong output** rather than an error.

### Fixed

- **Rotation was never read (silent wrong orientation).** `probe` looked for
  `tags.rotate`, but ffmpeg 8 puts the display matrix in
  `side_data_list[].rotation`. A 720x1280 clip tagged 90° *displays* as
  1280x720 landscape; vidscope reported `rotation: None`, `orientation:
  portrait`, `is_9_16: True`, and emitted no ASPECT flag. Orientation,
  aspect and resolution now all compute from display dimensions, and the
  ASPECT flag shows the stored size and rotation for transparency.
- **Freezes running to EOF were dropped entirely.** `freezedetect` only emits
  `freeze_end` when the freeze actually ends. A 3-second still frame logged
  `freeze_start` alone; the parallel-array parser dropped it and reported
  `flags: []`. A clip that stops moving before it stops playing now raises
  `FROZEN — from Xs to end of clip`.
- **Crushed-black threshold was off by one code value.** Pure black sits at
  luma 16 exactly; `y_min <= 16` only caught pixels strictly darker than that,
  so genuinely crushed frames went uncounted. Now uses `<= 17` combined with a
  near-black mean.
- **`brief` claimed "drop 0" when the source was simply too short.** It now
  states how many seconds short the source is and what to do about it, and
  pluralises "beat/beats" correctly.

### Testing

- Added `tests/adversarial.py` — 22 checks covering missing/empty/non-video
  files, audio-only input, 1-frame clips, out-of-range and over-supplied
  timestamps, unicode paths, rotation, low fps, concurrent runs, freeze-to-EOF,
  and JSON purity.
- The suite was **verified to fail against the reintroduced bugs**. Its first
  version hardcoded the repo path, so it silently tested a different directory
  and reported 22/22 on broken code — that flaw is fixed and documented.

## 1.0.0 — 2026-11-17

First public release.

**Commands**
- `vidscope probe` — scene cuts with exact timestamps, black/freeze intervals,
  luma statistics, and action-worded flags (silent, black, frozen, dark,
  overexposed, aspect, low-res, sub-HD, short).
- `vidscope sheet` — contact sheets at rung 1 (330px), 2 (760px), 3 (1080px),
  with a JSON sidecar recording the exact timestamp of every cell.
- `vidscope brief` — Markdown brief with pacing analysis, beat table, greedy
  segment selection against a target length, and a pre-filled vision prompt.

**Packaging**
- `skill/SKILL.md` — drop-in agent skill with trigger conditions and judgement,
  not just binaries.
- `examples/agent_example.py` — a complete, runnable agent loop.

**Notable bugs fixed during development** (each would have produced silently
wrong output):
- `scdet` combined with `metadata=mode=print` reported zero scene cuts. scdet
  logs its own metadata to stderr; the chained filter silenced it.
- Frame grouping in the signalstats parser closed records on the wrong key,
  mixing values across frames and reporting 25/25 crushed blacks on a
  well-exposed clip.
- Aspect ratio and resolution were conflated: a 576x1024 clip passed the 9:16
  check while being far below native upload size. They are now independent
  flags.
- Contact sheets wrote temp files next to the input, which fails on read-only
  mounts. Now uses a system temp dir with guaranteed cleanup.
