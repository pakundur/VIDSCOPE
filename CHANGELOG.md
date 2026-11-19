# Changelog

## 1.0.4 — 2026-11-19

Positioning and evidence release. No behaviour change to any command; the
output of `probe`, `sheet` and `brief` is byte-identical to 1.0.3. What
changed is what the project says about itself, and why.

### Added — measurement

- **`docs/cut-detection-accuracy.md`** now leads the project. Cut precision
  **91/91** on 20 real stock clips (every reported cut checked against actual
  frame-to-frame difference), and cut recall **30/30** on constructed splices,
  where ground truth is arithmetic rather than inferred. Both numbers were
  already measured in 1.0.3; they were buried behind the README.
- **A "what is still not proven" section** sits directly under the results:
  no 4K, HDR, 10-bit, VFR or long-form; no dissolves, wipes or fades. Publishing
  the untested cases is the point of the document.
- **The `scdet` duplicate-frame limitation** is documented with frame-level
  evidence. A cut followed by a byte-identical duplicate scores 0.000 and goes
  unreported. Characterised, not fixed.

### Added — positioning docs

- **`docs/positioning.md`** records the position, the three claims in priority
  order, and every competitor that is conceded in writing (PySceneDetect is
  better at detection; the agent-video space is crowded; "zero dependencies" is
  not unique). Also lists the conditions under which the position would become
  false.
- **`docs/showing-this-to-someone.md`** holds a Show HN draft, a CV line,
  answers to the four questions a reviewer will actually ask, and a "what not
  to say" list.
- **`docs/repo-metadata.md`** carries the About description and all 20 GitHub
  topics, with the reason each was chosen. GitHub's default search matches only
  name, description and topics, so these three fields matter more than README
  prose.

### Changed — README

- Opens on the measured accuracy table instead of a feature narrative. A
  visitor sees results before prose.
- New **"What this is, and what it is not"** section, placed before the install
  instructions, conceding PySceneDetect and the agent-video competitors by name
  and link.
- **Security** section states that the package contains zero URLs, zero pip
  dependencies, no `shell=True`, and no temp files beside the input.
- Em dashes removed from all prose. The remaining eleven are inside literal tool
  output and code comments.

## 1.0.3 — 2026-11-17

Closes the last two gaps from the 1.0.2 review: the sidecar could not describe
the render it produced, and nothing asserted that `sheet` honours rotation.

### Added — `sheet`

- **`sheet_width` / `sheet_height` in the sidecar.** An agent can now confirm
  the render kept cells at `cell_px` and used display orientation without
  re-probing the JPEG. (Applies to the sheet `_build_tiles` writes; the
  single-frame early-out copies the still, so dims follow the source frame.)

### Fixed — test harness

- **The sheet's rotation handling was untested.** `vd_sheet.py` contains no
  rotation code at all — it relies entirely on ffmpeg's auto-rotate — so
  adding `-noautorotate` anywhere in the extract path silently produces
  sideways cells. New check **12b** renders a 90°-tagged portrait clip at
  rung 3 and asserts the sheet comes out **landscape** (wider than tall) and
  that the sidecar dimensions match the file on disk.
  Verified to bite: injecting `-noautorotate` yields
  `FAIL rotated clip renders landscape sheet <- sheet=1228x2172`.
  Suite is now **28 checks**.

## 1.0.2 — 2026-11-17

Sheet-layer fixes (unchanged since 1.0.0) plus a false-green path in the test
harness. Every one of these produced confident, wrong output.

### Fixed — `sheet`

- **Rung 1 only sampled the first ~16 seconds.** `range(int(dur/step))[:n]`
  built a full 0..dur list and then kept the first n entries, so a 130s clip
  was represented by 0-15s and **88% of the video was never shown**. Rung 1 now
  uses `auto_times(dur, n)`, matching what the README always promised: t=0 and
  t=duration-0.15, spread evenly. A 130s clip now reports max_time=129.85.
- **Rung 3 downscaled landscape footage.** `scale={cell}:-2` pins WIDTH, so
  1920x1080 became 1080x608 — at the one rung whose entire job is reading a
  label. Now `scale=-2:{cell}` (pin height): cells are 1926x1086.
- **The tile stage could mask a broken per-frame scale.** It re-scaled every
  tile, so pinning width at the per-frame step looked fine in the final sheet.
  Both stages now use the same `-2:{cell}` form.
- **Seek mode is now explicit per rung.** Rung 3 seeks with `-ss` AFTER `-i`
  (decode-accurate) so a label is never read from the wrong frame; rungs 1-2
  keep the fast keyframe seek. The sidecar reports `seek_mode`.

### Fixed — sidecar truthfulness

- **The sidecar recorded requested times, not extracted frames.** When a seek
  failed, every later cell was labelled with the wrong timestamp — a vision
  model was then told frame 4 was at 999s when it was actually a valid frame
  from 40s. `times` now lists only frames that actually landed in the image, in
  cell order; `requested_times`, `clamped` and `failed_seeks` record the rest,
  plus `cells_filled`/`cells_expected`.

### Fixed — `probe` human output

- **Rotated clips printed self-contradictory dimensions**, e.g.
  `720x1280 (landscape)`. Now prints display dimensions with display
  orientation, and notes the stored size and rotation:
  `1280x720 (stored 720x1280, rotated 90°) (landscape)`.

### Fixed — test harness

- **The harness could report green having run zero tests.** When the
  developer's own clip was missing it printed `no source clip; abort` and
  returned, and `sys.exit(None)` is exit status 0 — so on any other machine,
  CI passed without executing a single check. It now synthesises a fixture with
  ffmpeg (`testsrc2`/`smptebars`/`testsrc` + sine audio, 12s, with real scene
  changes) and runs everything; it only exits non-zero if that is impossible.
- **Three checks protected the bugs above.** #7 asserted `rc == 0` for 30
  `--times` on a 4x4 grid, which is exactly what silent truncation looks like;
  #8 asserted `rc == 0` for out-of-range times and never read the sidecar; and
  #4 called `rec()` inside `if ok:`, so a failing exit reduced the total below
  27 instead of reporting a failure. All three now assert behaviour.
- Added checks 8c-8e (whole-clip coverage, landscape height, dims vs declared
  `cell_px`) and 23 (rotated human output consistency). Suite is now 27 checks
  and runs on any machine, with or without the author's footage.

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
