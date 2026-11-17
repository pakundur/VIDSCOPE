# VidScope

**See inside any video without watching it.**

VidScope is a small, dependency-free toolkit that tells you what is *actually*
in a video file — where the scene cuts are, whether the footage is broken, and
what is really on screen (products, actions, on-screen text, logos, faces).

It is built for two audiences at once:

- **Humans** — a CLI that prints a clear report you can read in seconds.
- **AI agents** — structured JSON designed to be handed to a vision model, with
  prompts pre-filled and timestamps precise.

```bash
$ vidscope probe clip.mp4

clip.mp4
  16.10s @ 30.0fps  720x1280 (portrait)  3.3 MB  h264
  audio streams: 1   scene cuts: 7
  FLAGS:
    ! SUB-HD — 720x1280; below the 1080x1920 native standard
```

---

## Why this exists

Everyone has a folder of video they need to check before publishing, editing,
or training on. Opening each one by hand is slow. Sampling "one middle frame"
is actively misleading — it is roughly 30% accurate about what a clip contains.

VidScope exists because of a specific, expensive failure: video tooling tends to
make **confident claims from downscaled evidence.** A 330px thumbnail makes
criss-cross fabric look like a logo. It makes a pot rim look like the word
"HOME". It makes colour-blocking look like an Adidas stripe. If you act on those
claims you either ship a competitor's brand, or throw away a perfectly good clip.

So VidScope is built around one rule:

> **A downscaled frame tells you *where to look*. Only full resolution tells you
> *what is there*.** Never let a cheap frame make a decision an expensive frame
> could overturn.

Every design choice below follows from that.

---

## Install

**Requirements:** Python 3.8+ and `ffmpeg` (with `ffprobe`) on your `PATH`.
Nothing else — no OpenCV, no numpy, no pip packages. Pure standard library.

```bash
git clone https://github.com/pakundur/vidscope.git
cd vidscope
./scripts/vidscope probe yourvideo.mp4
```

That is it — no install step. The CLI is a single executable file with three
sibling modules; it runs from the cloned directory exactly as-is.

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

Optional — put it on your `PATH`:

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

# 3. Read that sheet with any vision model / your own eyes
#    -> or let a model do it for you (works with Claude, GPT-4V, Gemini,
#       llava, Qwen-VL, or any multimodal endpoint)

# 4. Is there really text on that label? Confirm at full resolution.
vidscope sheet movie.mp4 --rung 3 --times 12.4 12.8

# 5. Plan a re-cut
vidscope brief movie.mp4 --target 21 34
```

---

## The two layers

VidScope deliberately separates **free measurement** from **paid interpretation**.

| Layer | Answers | Cost | Command |
|---|---|---|---|
| **Signal** | When do things change? Is it broken? | Free, ~2s, no model | `probe` |
| **Semantic** | What *is* it? Any text? Any faces? | One vision call | `sheet` + a model |

**Always run the signal layer first.** It is free, it catches unusable footage
before you spend anything describing it, and its scene-cut timestamps tell you
exactly which frames are worth sampling.

---

## Commands

### `probe` — technical forensics

```bash
vidscope probe VIDEO [--json]
```

Reports duration, fps, resolution, orientation, audio-stream count, **scene
cuts with exact timestamps**, black intervals, freeze intervals, and luma
statistics — plus a `FLAGS` block written as *actions*, not trivia.

**Flags you will see, and what to do:**

| Flag | Meaning | Action |
|---|---|---|
| `SILENT` | No audio stream | Add music; silent social video underperforms |
| `BLACK — 2.1s at 0.0s` | Black interval | Trim it — a black opening reads as a stall |
| `FROZEN — 2.6s at 64.1s` | Frozen frames | Cut the dead air; viewers read it as buffering |
| `DARK — 12/25 frames under luma 40` | Too dim | Regrade or reshoot; phone screens are bright |
| `ASPECT — 1920x1080` | Wrong orientation | Crop to 9:16 for Shorts/TikTok/Reels |
| `LOW-RES` / `SUB-HD` | Below native size | Upscaling will look soft next to native clips |
| `SHORT — 3.0s` | Very brief | Below the length that earns a watch |

**Cut density tells you what kind of video it is:**

| cuts/min | Interpretation |
|---|---|
| < 6 | Single continuous take — treat as one shot |
| 6–20 | Normal demo / dialogue pacing |
| 20–60 | Fast montage, roughly 1–3s per shot |
| > 60 | Hyper-cut, or the detector is firing on rapid motion rather than cuts |

> Scene scores are **not always real cuts.** A whip pan or a hand crossing frame
> scores like one. Confirm boundaries by looking.

---

### `sheet` — contact sheets at three resolutions

```bash
vidscope sheet VIDEO --rung {1,2,3} [--times T1 T2 ...] [--grid 4x4] [--out PATH]
```

| Rung | Cell size | Use it for | What it can answer |
|---|---|---|---|
| **1** | 330px | "What is this video?" | Story, faces, arc, presence of a payoff |
| **2** | 760px | Framing, product ID, obvious text | What is being shown, where text sits |
| **3** | 1080px | **Confirming a suspect label** | Exact letters — yes or no |

Each sheet writes a `.json` sidecar. It records `times` — the frames **actually
in the image**, in cell order — plus `requested_times`, `cells_filled`,
`cells_expected`, `seek_mode`, and any `clamped` or `failed_seeks`. Label cells
from `times`, never from what you asked for: a failed seek would otherwise
shift every later label against its cell.

> **Rung 1 is a triage resolution, never a verification resolution.** At 330px
> you cannot read a label, a watermark, or a brand name. You can only see that
> something *might* be there. That is exactly what it is for — and it is never
> enough to decide.

---

### `brief` — a readable report and a segment plan

```bash
vidscope brief VIDEO [--target 21 34]
```

Produces a Markdown brief: structure and pacing, image-quality summary, defects,
candidate beats as a table, and a **pre-filled vision prompt** containing the
real timestamps of the frames you are about to show a model.

The `--target` band greedily selects beats to land inside a length window
(21–34s is the short-form social sweet spot; 15–21s for ads).

> A segment plan is a **proposal**. Boundaries come from scene detection, so they
> land where pixels changed — not where the story beat is. Sanity-check against
> the sheet.

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

**Sample both ends.** A mid-clip-only sheet misses frame 0 (the hook) and the
last frame (the payoff). VidScope always includes `t=0` and `t=duration-0.15`.

### Worked example — the same rule, twice, in opposite directions

On real footage, a vision model reported **"Adidas three-stripe logo"** on a
shoe. Full-resolution zoom showed generic colour-blocking. **The brand did not
exist.** Acting on the sheet would have cost a clean clip.

On a different clip, the model reported **老干妈 (Lao Gan Ma)** on a jar. Full
resolution confirmed it — plus `280g` and printed dates. **The brand was real.**
Acting on the sheet would have shipped a third-party trademark.

Vision also invented `TEA`, `GRAND`, `HOME`, `ON`, and `FASHION` on other clips.
Every one was disproven at full resolution.

**The sheet was right once and wrong once.** That is the whole argument: a
downscaled frame is a lead-generator with a coin-flip error rate in both
directions, so it can never be the deciding vote.

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
3. **Ask forced-choice questions** — *"is it (a) brand X, (b) another brand,
   (c) generic?"* — and always offer "no text" as an option. Open questions
   invite invention.
4. **Report scope honestly.** "No text in 16 sampled frames" is not "no text
   anywhere". Say which one you did.

`brief` generates a prompt that already follows these rules — prefer it over
writing your own.

---

## Use as a skill for Claude / ChatGPT / any agent

This repository is also packaged as a drop-in **agent skill**. Copy the folder
into your skills directory and the agent will know when and how to use it:

```bash
# Claude Code / Claude Desktop skills
cp -r skill/ ~/.claude/skills/vidscope/

# Hermes Agent
cp -r skill/ ~/.hermes/skills/creative/vidscope/
```

The skill file (a `SKILL.md` with YAML frontmatter) contains the trigger
conditions, the three-rung discipline, the verification gate, and the pitfalls —
so an agent loads the *judgement*, not just the binaries.

---

## What VidScope does NOT tell you

Being clear about the limits is part of being trustworthy:

- **Audio content** — you get a stream count, not speech or music. Transcribe
  separately if you need words.
- **Motion quality** — blur, judder, stabilisation are not measured.
- **Whether a payoff *lands*** — a sheet can show a clean final frame without
  revealing that it arrives half a second before the end, too late to register.
- **Off-frame text** — a UI element may be outside the still but pan in later.
  Sample densely if the camera moves.
- **Semantic truth** — it measures pixels and hands frames to a model. It does
  not *know* what a product is.

---

## Tested on

- Samsung Galaxy S25 Ultra, **Android 17 / Termux** (aarch64), ffmpeg 8.1.2
- Debian, macOS, and Windows via the same stdlib-only code path
- Clips from 3s to 130s, 576×1024 to 1080×1920, silent and with audio

Real defects caught in testing: a **2.6s freeze at 64.1s** in a 130s
compilation, and a **576×1024 clip** that passed every aspect check but would
have upscaled badly onto a 1080×1920 timeline.

---

## Repository layout

```
vidscope/
├── scripts/
│   ├── vidscope          # the CLI you call (dispatcher)
│   ├── vd_probe.py       # signal layer  — scenes, black, freeze, luma, flags
│   ├── vd_sheet.py       # contact sheets — rung 1 / 2 / 3
│   └── vd_brief.py       # brief + segment plan + vision prompt
├── skill/SKILL.md        # drop-in agent skill (Claude, Hermes, any agent)
├── examples/
│   └── agent_example.py  # a complete agent loop, runnable
├── tests/
│   └── adversarial.py    # 28 checks that try to break it
└── docs/
    └── worked-example.md # one clip, three rungs, one real finding
```

Each `vd_*.py` module also runs standalone, so you can call or import it
directly instead of going through the dispatcher.

## Tests

```bash
python3 tests/adversarial.py
```

28 checks that try to break the tool: missing, empty and non-video files,
audio-only input, single-frame clips, out-of-range and over-supplied
timestamps, unicode paths, rotated streams, low frame rates, concurrent runs,
freezes that run to end-of-file, whole-clip rung-1 coverage, landscape rung-3
resolution, rotated streams rendering a correctly-oriented sheet, and
sidecar/label agreement.

It needs no fixtures — if the author's sample clip is absent it synthesises one
with ffmpeg and runs everything anyway.

Every check asserts a **behaviour**, not just an exit code — the first version
of this suite passed 22/22 against code with three known bugs in it, because
two assertions only verified `returncode == 0`. The suite has since been run
against deliberately reintroduced bugs to confirm it actually fails.

## Contributing

Issues and PRs welcome — especially **new detectors** (blur, shake, letterbox,
duplicate-frame detection) and **new vision backends** in `docs/`.

If you add a check, add a flag with an *action*, not just a measurement. The
value of this tool is that it tells you what to do.

## License

MIT — see [LICENSE](LICENSE).
