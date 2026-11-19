# VidScope

**Video forensics a script can trust: cuts, black, freeze and luma in one JSON call, with every claim measured and every limit documented.**

Most video tools tell you what they found. VidScope tells you what it found, how it was measured, and which cases it has never been tested on.

```bash
$ vidscope probe clip.mp4 --json
```
```json
{
  "clips": { "duration_s": 23.321, "display_width": 480,
             "display_height": 854, "orientation": "portrait" },
  "scene": { "frames_scored": 582, "cuts_detected": 9,
             "cuts_per_minute": 23.2, "shot_length_median_s": 2.68 },
  "black": [],
  "freeze": [ { "start": 20.321, "end": 23.321, "duration": 3.0,
                "runs_to_eof": true } ],
  "luma": { "y_avg_mean": 162.86, "crushed_black_frames": 0,
            "blown_white_frames": 0 },
  "flags": [ "FROZEN — 3.0s at 20.3s; viewers read this as buffering",
             "LOW-RES — 480x854; upscaling to 1080x1920 will look soft" ]
}
```

That is real output from a real 23 second product video. It caught a 3 second static end card that reads as a stalled player, and a 480px source that cannot be upscaled cleanly.

---

## Accuracy, stated up front

Most tools in this space publish no accuracy figure at all. These are measured against ground truth, not estimated.

| Measurement | Result | Method |
|---|---|---|
| Cut **precision** | **91 / 91** (100%) | 20 real stock clips, each reported cut checked frame by frame |
| Cut **recall** | **30 / 30** (100%) | 30 cuts constructed by splicing, so ground truth is arithmetic |
| Black detection | **0 mismatches / 20 clips** | Scored against raw `blackdetect` output |
| Freeze detection | **0 mismatches / 20 clips** | Scored against raw `freezedetect` output |
| Luma tracking | within **0.06** | Independent ffmpeg sampling |

**Read the limits before trusting the numbers.** Recall was measured on hard cuts between visually distinct shots. Dissolves, wipes and fades are **not** represented and `scdet` is not designed to find them. All footage was short portrait social video, no 4K, HDR, 10-bit, VFR or long-form is covered. Full method, including one genuine ffmpeg limitation found during testing: [`docs/cut-detection-accuracy.md`](docs/cut-detection-accuracy.md).

A measurement that never appears anywhere is worth as much as no measurement. Publishing the untested cases is the point.

---

## What this is, and what it is not

**It is** a dependency-free measurement layer. It answers "is this file usable, where does it change, what is technically wrong with it" in about a second, with structured output an agent can read directly.

**It is not** a scene-detection library, and you should not pick it for that. [`PySceneDetect`](https://github.com/Breakthrough/PySceneDetect) is better at detection than VidScope is: BSD-3, active since 2014, multiple detectors including adaptive handling for fast camera movement and a threshold detector for fades, plus splitting, image export, a Python API and a Docker image. If detection quality is your problem, use it. VidScope wraps one ffmpeg filter and a hand-tuned threshold, and that is a genuinely narrower thing.

**It is not** an "AI agent watches video" toolkit either. [`claude-real-video`](https://github.com/yetio/claude-realtime-video), [`agentic-video`](https://github.com/tlq5l/agentic-video), [`popcorn`](https://github.com/haithamelmengad/popcorn), [`watch-video`](https://github.com/TomGranot/watch-video) and a dozen others already do frame sampling, transcription and contact sheets, most with more features and MCP servers.

### So why does this exist

Three honest reasons.

**1. It runs where nothing else will.** Pure standard library plus `ffmpeg`. No pip, no venv, no API key, no Docker, no Node. It was developed and measured on a Samsung Galaxy S25 Ultra in Termux, which is a hostile environment for the rest of this category. On a locked-down machine, a phone, or a box where you cannot install anything, that narrows the field to about one.

**2. One call, one object.** Duration, cuts with timestamps, black, freeze, luma and actionable flags come back together as JSON. Competitors split this across separate commands, GUI tools, or log parsing.

**3. The evidence discipline.** Precision and recall are measured against constructed ground truth and published with their limits. That is the actual differentiator, and it is the reason this document leads with a table of results instead of a feature list.

---

## Install

**Requirements:** Python 3.8+ and `ffmpeg` (with `ffprobe`) on your `PATH`. Nothing else, no OpenCV, no numpy, no pip packages.

```bash
git clone https://github.com/pakundur/VIDSCOPE.git
cd VIDSCOPE
./scripts/vidscope probe yourvideo.mp4
```

No install step. The CLI is an executable file with three sibling modules and runs from the cloned directory as-is.

<details>
<summary>Installing ffmpeg</summary>

| Platform | Command |
|---|---|
| Debian / Ubuntu | `sudo apt install ffmpeg` |
| macOS | `brew install ffmpeg` |
| Windows | `winget install ffmpeg` or [ffmpeg.org/download](https://ffmpeg.org/download.html) |
| Android / Termux | `pkg install ffmpeg` |
| Arch | `sudo pacman -S ffmpeg` |

</details>

Optional, put it on `PATH`:

```bash
sudo ln -s "$PWD/scripts/vidscope" /usr/local/bin/vidscope
```

---

## Sixty-second quickstart

```bash
# 1. What is this file, and is it broken?
vidscope probe movie.mp4

# 2. Show me what's in it (builds a contact sheet)
vidscope sheet movie.mp4 --rung 1

# 3. Read that sheet with any vision model, or your own eyes

# 4. Is there really text on that label? Confirm at full resolution.
vidscope sheet movie.mp4 --rung 3 --times 12.4 12.8

# 5. Plan a re-cut
vidscope brief movie.mp4 --target 21 34
```

---

## The two layers

VidScope separates **free measurement** from **paid interpretation**.

| Layer | Answers | Cost | Command |
|---|---|---|---|
| **Signal** | When do things change? Is it broken? | Free, ~2s, no model | `probe` |
| **Semantic** | What *is* it? Any text? Any faces? | One vision call | `sheet` + a model |

**Always run the signal layer first.** It is free, it catches unusable footage before you spend anything describing it, and its cut timestamps tell you exactly which frames are worth sampling.

---

## Commands

### `probe`: technical forensics

```bash
vidscope probe VIDEO [--json]
```

Reports duration, fps, resolution, orientation, audio-stream count, **cuts with exact timestamps**, black intervals, freeze intervals and luma statistics, plus a `FLAGS` block written as *actions*, not trivia.

The `scene` block carries two pacing fields, because a cut count says little alone: 8 cuts in 10s and 8 cuts in 30s are different videos. `cuts_per_minute` and `shot_length_median_s` compare directly between clips. `mean_score` separates a static shot from a busy one by itself; across 20 stock clips it ranged 0.21 to 0.92, and every single-take clip sat under 0.35.

**Flags you will see, and what to do:**

| Flag | Meaning | Action |
|---|---|---|
| `NO-VIDEO` | No video stream at all | Audio-only file; nothing to look at |
| `SILENT` | No audio stream | Add music; silent social video underperforms |
| `BLACK — 2.1s at 0.0s` | Black interval | Trim it, since a black opening reads as a stall |
| `FROZEN — 2.6s at 64.1s` | Frozen frames | Cut the dead air; viewers read it as buffering |
| `DARK — 12/25 frames under luma 40` | Too dim | Regrade or reshoot; phone screens are bright |
| `ASPECT — 1920x1080` | Wrong orientation | Crop to 9:16 for Shorts/TikTok/Reels |
| `LOW-RES` / `SUB-HD` | Below native size | Upscaling will look soft next to native clips |
| `SHORT — 3.0s` | Very brief | Below the length that earns a watch |

**Cut density tells you what kind of video it is:**

| cuts/min | Interpretation |
|---|---|
| < 6 | Single continuous take, treat as one shot |
| 6–20 | Normal demo / dialogue pacing |
| 20–60 | Fast montage, roughly 1–3s per shot |
| > 60 | Hyper-cut, or the detector is firing on rapid motion rather than cuts |

> Scene scores are **not always real cuts.** A whip pan or a hand crossing frame scores like one. Confirm boundaries by looking.

**Known limitation, measured:** `scdet` scores each frame against its predecessor. A cut immediately followed by a byte-identical duplicate frame scores 0.000 and is not reported. Reproduced with frame-level data in the accuracy doc.

---

### `sheet`: contact sheets at three resolutions

```bash
vidscope sheet VIDEO --rung {1,2,3} [--times T1 T2 ...] [--grid 4x4] [--out PATH]
```

| Rung | Cell size | Use it for | What it can answer |
|---|---|---|---|
| **1** | 330px | "What is this video?" | Story, faces, arc, presence of a payoff |
| **2** | 760px | Framing, product ID, obvious text | What is shown, where text sits |
| **3** | 1080px | **Confirming a suspect label** | Exact letters, yes or no |

Each sheet writes a `.json` sidecar recording `times`, the frames **actually in the image**, in cell order, plus `requested_times`, `cells_filled`, `cells_expected`, `seek_mode`, and any `clamped` or `failed_seeks`. Label cells from `times`, never from what you asked for: a failed seek would otherwise shift every later label against its cell.

> **Rung 1 is a triage resolution, never a verification resolution.** At 330px you cannot read a label, a watermark or a brand name. You can only see that something *might* be there. That is what it is for, and it is never enough to decide.

---

### `brief`: a readable report and a segment plan

```bash
vidscope brief VIDEO [--target 21 34]
```

Produces a Markdown brief: structure and pacing, image-quality summary, defects, candidate beats as a table, and a **pre-filled vision prompt** containing the real timestamps of the frames you are about to show a model.

`--target` greedily selects beats to land inside a length window (21–34s is the short-form social sweet spot; 15–21s for ads).

> A segment plan is a **proposal**. Boundaries come from scene detection, so they land where pixels changed, not where the story beat is. Sanity-check against the sheet.

---

## The three-rung discipline

This is the part that matters. It is cheap and it prevents the expensive error.

```
RUNG 1  (330px, 1fps)
        └─ "Is there something on the label?"
               │
               ▼
RUNG 2  (760px, 5 sample points: 0%, 15%, 35%, 55%, 75%, 92%)
        └─ "Yes — text persists. Which frames, where in frame?"
               │
               ▼
RUNG 3  (1080px, exact timestamps, tight crop)
        └─ "Read the actual letters. Does it say 老干妈, or not?"
```

**Sample both ends.** A mid-clip-only sheet misses frame 0 (the hook) and the last frame (the payoff). VidScope always includes `t=0` and `t=duration-0.15`.

### Worked example : the same rule, twice, in opposite directions

On real footage, a vision model reported **"Adidas three-stripe logo"** on a shoe. Full-resolution zoom showed generic colour-blocking. **The brand did not exist.** Acting on the sheet would have cost a clean clip.

On a different clip, the model reported **老干妈 (Lao Gan Ma)** on a jar. Full resolution confirmed it, plus `280g` and printed dates. **The brand was real.** Acting on the sheet would have shipped a third-party trademark.

Vision also invented `TEA`, `GRAND`, `HOME`, `ON` and `FASHION` on other clips. Every one was disproven at full resolution.

**The sheet was right once and wrong once.** That is the whole argument: a downscaled frame is a lead generator with a coin-flip error rate in both directions, so it can never be the deciding vote.

📄 Full run-through: [`docs/worked-example.md`](docs/worked-example.md)

---

## Using VidScope with an AI agent

VidScope is designed to be called *by* a model, not just read by a human.

```python
import json, subprocess

# 1. free triage — no model tokens spent
probe = json.loads(subprocess.run(
    ["vidscope", "probe", "clip.mp4", "--json"],
    capture_output=True, text=True).stdout)

if probe["flags"]:
    print("Fix these first:", probe["flags"])   # don't describe broken footage

# 2. build a sheet at the frames the detector says matter
top_cut = probe["scene"]["top_cuts"][0]["time"]
subprocess.run(["vidscope", "sheet", "clip.mp4",
                "--rung", "3", "--times", str(top_cut)])

# 3. ask a vision model, then ESCALATE every text claim to full res
```

**Agent rules of thumb:**

1. **Probe before you look.** Zero cost, catches broken files early.
2. **Never reject or accept on a rung-1/2 text claim.** Escalate to rung 3.
3. **Ask forced-choice questions**, *"is it (a) brand X, (b) another brand, (c) generic?"*, and always offer "no text" as an option. Open questions invite invention.
4. **Report scope honestly.** "No text in 16 sampled frames" is not "no text anywhere". Say which one you did.

`brief` generates a prompt that already follows these rules; prefer it over writing your own.

---

## Use as a skill for Claude / ChatGPT / any agent

Packaged as a drop-in **agent skill**. Copy the folder into your skills directory and the agent knows when and how to use it:

```bash
# Claude Code / Claude Desktop skills
cp -r skill/ ~/.claude/skills/vidscope/

# Hermes Agent
cp -r skill/ ~/.hermes/skills/creative/vidscope/
```

The skill file (`SKILL.md` with YAML frontmatter) contains the trigger conditions, the three-rung discipline, the verification gate and the pitfalls, so an agent loads the *judgement*, not just the binaries.

---

## Security

Built to be auditable, because it runs on your files:

- **Zero URLs** in the entire package. No telemetry, no update check, no network call of any kind.
- **Zero pip dependencies.** Standard library only.
- **No `shell=True`** anywhere. Every subprocess call takes an argument list.
- **Reads only the file you name.** Writes only the `--out` path you name.
- **No temp files** created beside your input.

---

## What VidScope does NOT tell you

- **Audio content**, you get a stream count, not speech or music. Transcribe separately.
- **Motion quality**, blur, judder, stabilisation are not measured.
- **Whether a payoff *lands***, a sheet can show a clean final frame without revealing that it arrives half a second before the end.
- **Off-frame text**, a UI element may be outside the still but pan in later.
- **Semantic truth**, it measures pixels and hands frames to a model. It does not *know* what a product is.
- **Dissolves, wipes, fades**, not detected, and not claimed to be.

---

## Tested on

- Samsung Galaxy S25 Ultra, **Android 17 / Termux** (aarch64), ffmpeg 8.1.2
- Debian, macOS and Windows via the same stdlib-only code path
- Clips from 3s to 130s, 576×1024 to 1080×1920, silent and with audio

Real defects caught in testing: a **2.6s freeze at 64.1s** in a 130s compilation, and a **576×1024 clip** that passed every aspect check but would have upscaled badly onto a 1080×1920 timeline.

---

## Repository layout

```
VIDSCOPE/
├── scripts/
│   ├── vidscope          # the CLI you call (dispatcher)
│   ├── vd_probe.py       # signal layer — scenes, black, freeze, luma, flags
│   ├── vd_sheet.py       # contact sheets — rung 1 / 2 / 3
│   └── vd_brief.py       # brief + segment plan + vision prompt
├── skill/SKILL.md        # drop-in agent skill
├── examples/
│   └── agent_example.py  # a complete agent loop, runnable
├── tests/
│   ├── adversarial.py    # 28 checks that try to break it
│   ├── mine_segments.py  # build single-shot segment pool
│   └── recall_spliced.py # construct cuts, measure recall
└── docs/
    ├── cut-detection-accuracy.md      # precision, recall, and what is unproven
    ├── stock-corpus-test-2026-11-19.md # the 20-clip verification run
    └── worked-example.md               # one clip, three rungs, one real finding
```

Each `vd_*.py` module also runs standalone, so you can call or import it directly instead of going through the dispatcher.

## Tests

```bash
python3 tests/adversarial.py     # 28 checks, no corpus needed
python3 tests/recall_spliced.py  # 30 constructed cuts, needs a clip corpus
```

`adversarial.py` covers missing, empty and non-video files, audio-only input, single-frame clips, out-of-range and over-supplied timestamps, unicode paths, rotated streams, low frame rates, concurrent runs, freezes that run to end-of-file, whole-clip rung-1 coverage, landscape rung-3 resolution, rotated streams rendering a correctly-oriented sheet, and sidecar/label agreement. It needs no fixtures; if the sample clip is absent it synthesises one with ffmpeg.

Every check asserts a **behaviour**, not just an exit code. The first version of this suite passed 22/22 against code with three known bugs in it, because two assertions only verified `returncode == 0`. The suite has since been run against deliberately reintroduced bugs to confirm it actually fails.

## Contributing

Issues and PRs welcome, especially **new detectors** (blur, shake, letterbox, duplicate-frame detection) and **new vision backends**.

If you add a check, add a flag with an *action*, not just a measurement. The value of this tool is that it tells you what to do.

**If you report an accuracy claim, say how you measured it.** Guessed numbers are worse than no numbers.

## License

MIT, see [LICENSE](LICENSE).
