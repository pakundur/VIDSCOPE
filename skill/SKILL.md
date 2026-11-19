---
name: vidscope
description: Use when you need to understand or verify a video file's content without watching it. Detect scene cuts, black/frozen frames, exposure faults, and read what is actually on screen (products, actions, on-screen text, logos, faces). Load for "what's in this video", "check this clip before I post", "detect scenes", "does this video have text/faces", "is this clip usable", or any pre-publish / pre-edit audit.
license: MIT
---

# VidScope: Video Frame Detection & Content Understanding

Turn an opaque video file into facts you can act on: what happens, when,
whether it is technically sound, and whether it is safe to ship.

## When to use

- **"What's in this video?"**: describe content, beats, product, setting.
- **Pre-publish audit**: verify no faces, logos, watermarks, on-screen text.
- **Pre-edit triage**: find usable segments and cut points before cutting.
- **Quality check**: catch black frames, freezes, bad exposure, wrong aspect.
- **Batch triage**: screen 50 clips for which are worth watching.

Do NOT use this for editing itself. This is measurement, not cutting.

## Setup

Requires `ffmpeg` + `ffprobe` on `PATH` and Python 3.8+. Pure standard
library. No OpenCV, no numpy, no pip installs.

```bash
vidscope --help
```

If the `vidscope` command is not available, call the scripts directly from the
repository root: `python3 scripts/vidscope COMMAND ...`.

## The two layers, and the order to run them

| Layer | Answers | Tool | Cost |
|---|---|---|---|
| **Signal** | when do things change? is it broken? | `vidscope probe` | seconds, no LLM |
| **Semantic** | what IS it? any text? any faces? | `vidscope sheet` + vision | one image read |

**Always run the signal layer first.** It is free; it tells you which frames
are worth spending a vision call on. Jumping straight to vision on a 60s video
wastes calls on frames where nothing changes.

## Step 1: Signal pass

```bash
vidscope probe clip.mp4          # human-readable
vidscope probe clip.mp4 --json   # for agents / piping
```

Emits duration, fps, resolution, orientation, audio-stream count, scene cuts
with exact timestamps, black intervals, freeze intervals, luma stats, and a
`FLAGS` block written as actions.

**Read the flags, not just the numbers:**

- `SILENT` → no audio stream; needs music added downstream
- `BLACK — 2.1s at 0.0s` → trim it; a black open reads as a stall
- `FROZEN — 2.6s at 64.1s` → viewers read it as buffering; cut the dead air
- `DARK — 12/25 frames under luma 40` → too dim for phone screens
- `ASPECT — 1920x1080` → needs a 9:16 crop for vertical platforms
- `LOW-RES` / `SUB-HD` → **aspect and resolution are independent.** 576×1024 is
  a valid 9:16 yet still looks soft upscaled to 1080×1920. A clip can pass the
  aspect test and fail resolution.
- `SHORT — 3.0s` → below the length that earns a watch

**Cut density:**

| cuts/min | meaning |
|---|---|
| < 6 | single continuous take, treat as ONE shot |
| 6–20 | normal demo/dialogue pacing |
| 20–60 | fast montage, ~1–3s per shot |
| > 60 | hyper-cut, or the detector is firing on motion not cuts |

High scores are not always real cuts. A whip pan or a hand crossing frame
scores like one. Confirm boundaries by looking.

## Step 2: Contact sheet and vision

| Rung | Cell | Use for | Answers |
|---|---|---|---|
| 1 | 330px | "what is this video?" | story, faces, arc, payoff |
| 2 | 760px | framing, obvious text, product | product ID, action, text leads |
| 3 | 1080px | **confirm a suspect label** | exact letters yes/no |

```bash
vidscope sheet clip.mp4 --rung 1
vidscope sheet clip.mp4 --rung 3 --times 5.0 5.5 6.0
```

Writes `clip_rungN.jpg` plus a `.json` sidecar recording the exact timestamp of
every cell. Then read the sheet with a vision model:

```
vision(sheet.jpg, question="<prompt from vidscope brief>")
```

`vidscope brief` generates that prompt already containing the real timestamps, so
prefer it over writing your own.

### The 330px trap, where bad clips get shipped

**330px is triage, never verification.** At 330px you cannot read a label, a
watermark, or a brand. You can only see that something *might* be there,
which is exactly the point, and never enough to decide.

Escalate every text finding to rung 3 at the exact timestamp before it changes
what you do:

```
rung 1 (330)  →  "there's text on the container"
rung 2 (760)  →  0/15/35/55/75/92%. Does the text persist, and where?
rung 3 (1080) →  zoom the suspect region, read the actual letters
```

### Vision invents text, so every hit is a LEAD, never a finding

Observed on real footage: a model reported "TEA", "GRAND", "HOME", "ON",
"FASHION", and an entire "Adidas three-stripe logo", **all disproven at full
resolution.** Stitching, bezels, fabric patterns, and colour-blocking read as
lettering to a downscaled eye.

But the opposite happens too: the same model reported **老干妈 (Lao Gan Ma)** on
a jar, and full resolution **confirmed it**, plus `280g` and printed dates.

**The sheet was wrong once and right once.** That is why it can never be the
deciding vote in either direction.

**Rule:** never reject or accept a clip on a sheet-based text claim. Zoom first.

```bash
# consecutive full-res frames around the suspect second
vidscope sheet clip.mp4 --rung 3 --times 5.0 5.4 5.8 6.2
```

Ask a **forced-choice** question ("is it (a) brand X, (b) another brand,
(c) generic") and always offer "no text" as an option. Open questions invite
invention.

### What tiles do NOT show you

- **Audio**: a stream count, not speech or music.
- **Motion quality**: blur, judder, stabilisation.
- **Whether the payoff lands**: a clean frame may arrive 0.5s before the end,
  too late to register.
- **Off-frame text**: a UI element out of frame in the still may pan in later.
  Sample densely if the camera moves.

## Step 3: Segment plan

```bash
vidscope brief clip.mp4 --target 21 34
```

Produces a beat table (start/end/len per segment) and greedily selects beats to
land inside the target band. 21–34s is the short-form social sweet spot;
15–21s for ads.

**A segment plan is a proposal.** Boundaries come from the scene detector, so
they land where pixels changed, not where the story beat is. Sanity-check
against the sheet: if beat 2 is "product introduced", does the frame at its
midpoint actually show the product?

## Verification gate, before claiming a video is clean

1. `probe` → no BLACK over 0.5s, no FREEZE over 1.5s, no DARK flag
2. Rung 1 sheet read → story identified, product named
3. Rung 3 zoom on **every** frame where text or branding was reported
4. Faces confirmed absent (actively checked, not merely "not seen")
5. Aspect ratio and resolution match the destination
6. Audio: silent is fine only if music will be added

Claim what you verified and only what you verified. "No text found in 16
sampled frames" ≠ "no text anywhere". Say which one you did.

## Pitfalls

### ffmpeg / scdet
- **`scdet` takes two thresholds and both drop frames.** `s=` is the scene
  score floor (0–100); `t=` is the scene time window in seconds over which the
  score is accumulated. `scdet=s=1:t=1` logs only frames scoring above 1/100.
  On a 301-frame clip measured here, 2 frames survived, so any statistic
  derived from the log described the surviving tail rather than the clip. Use
  `scdet=s=0:t=0` to log every frame at per-frame resolution.
- **`metadata=mode=print` after scdet does not silence it.** It emits
  `lavfi.scd.score` a second time as `key=value`, so a parser matching both
  `score:` and `score=` counts every frame twice. Match one form only.
- **Parse metadata as blocks, not lines.** Each frame is a `pts_time:` header
  followed by `mafd=`, `score=`, `time=` on separate lines, with scdet's own
  line for the next frame interleaved between blocks. A line-at-a-time parse
  returns a score with no timestamp, and a cut loop that requires a timestamp
  then drops every cut while still reporting a correct frame count.
- **`lavfi.scd.time` gives the exact timestamp**, so use it instead of
  interpolating `frame_index × duration / frames`, which drifts.
- **Rotation lives in side data, not tags.** ffmpeg 8 no longer populates
  `tags.rotate`; the display matrix shows up as
  `side_data_list[].rotation`. A 720×1280 stream tagged 90° is *displayed*
  1280×720, so check side data first, fall back to the tag, and compute
  orientation/resolution from the **display** dimensions. Otherwise a landscape
  video in a portrait container is silently treated as 9:16.
- **`freezedetect` only emits `freeze_end` when the freeze ends.** A clip
  frozen *at EOF* logs `freeze_start` alone. Parsing starts/ends as parallel
  arrays drops it entirely, so a 3-second still frame passes as clean. That is the
  worst miss, since a video that stops moving before it stops playing reads as
  a hang. Track open intervals and close any still open using the clip duration.
- **`signalstats` emits YMIN→YMAX per frame across separate lines.** Group per
  frame by opening a record on YMIN and closing on YMAX. Closing on an arbitrary
  key mixes values across frames and reports absurd clipping counts (e.g.
  "25/25 crushed black" on a well-exposed clip).

### Sheets
- **Include both ends.** A mid-clip-only sheet misses frame 0 (the hook) and the
  last frame (the payoff). Sample `t=0` and `t=duration-0.15`.
- **Spread samples across the WHOLE clip, not the first N seconds.**
  `range(int(dur/step))[:n]` is the trap: it builds 0..dur then keeps the first
  n entries, so a 130s clip is represented by its first 16s and 88% of the video
  is never seen. Use an even spread, e.g. `i*(dur-0.15)/(n-1)`.
- **Pin the SHORTEST side when downscaling.** `scale={cell}:-2` pins width, so
  1920x1080 becomes 1080x608, at the very rung whose job is reading a label.
  Use `scale=-2:{cell}` so height is pinned and landscape keeps its detail.
- **Check every scale stage.** A tile/overlay pass that re-scales silently masks
  a wrong scale in the extract stage: the final sheet looks fine while the
  frames were already destroyed. Both stages must use the same form.
- **Label cells from what was EXTRACTED, not what you requested.** A failed or
  clamped seek shifts every later cell against its label, and a vision model
  then reads frame 4 as "999s". Record actual times plus the requested list,
  cell counts and failures.
- **Seek mode matters at full res.** `-ss` before `-i` can return a frame up to
  a GOP early on some containers; for label-reading, seek AFTER `-i`.
- **Don't duplicate filler cells.** Padding a grid with a repeated last frame
  reads as a frozen section.
- **Rotation is fixed by ffmpeg's auto-rotate, not by code.** `vd_sheet.py` has
  no rotation logic. The extract step relies on ffmpeg honouring the display
  matrix. Anything that adds `-noautorotate` renders sideways cells with no
  error, and only a geometry assertion catches it: a portrait clip tagged 90°
  must produce a sheet **wider than tall**.
- **Don't tile more than ~16 cells at 760px+.** Output gets large and vision
  downscales it again, defeating the purpose.

### Reporting
- **Print display dimensions with display orientation.** Printing stored
  `720x1280` next to `(landscape)` is a self-contradiction the reader has to
  decode; print `1280x720 (stored 720x1280, rotated 90°) (landscape)`.

### Environment
- **A read-only temp dir will break the sheet step.** Pass `--out` to a writable
  directory if the default fails.
- **No headless browser needed.** This ffmpeg + vision route is the only visual
  verification required.

## Related

- Montage/editing mechanics belong in an editing skill, not here. VidScope
  produces the facts; something else produces the cut.
