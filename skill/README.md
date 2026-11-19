# VidScope

Video frame detection and content understanding for AI agents. It turns an
opaque video file into facts you can act on: what happens, when, whether it is
technically sound, and whether it is safe to ship.

This lets an agent answer "what is in this video?" without watching it.

## What it does

- Detects scene cuts with exact timestamps
- Finds black intervals and frozen frames
- Reports exposure faults, low resolution and wrong aspect ratio
- Builds a contact sheet with timestamps so a vision model can read what is
  actually on screen, including on-screen text, logos and faces
- Produces a segment plan inside a target duration band

## Requirements

- `ffmpeg` and `ffprobe` on `PATH`
- Python 3.8 or newer
- Pure standard library. No OpenCV, no numpy, no pip installs.

## Install

Copy the `vidscope/skill/` directory into your agent's skills directory, and
make `vidscope/scripts/` available on `PATH` (or call the scripts directly).

```bash
vidscope --help
```

If the `vidscope` command is not available, run it from the repository root:

```bash
python3 scripts/vidscope COMMAND ...
```

## Usage

```bash
vidscope probe clip.mp4            # signal pass, human readable
vidscope probe clip.mp4 --json     # machine readable
vidscope sheet clip.mp4 --rung 1   # contact sheet for a vision read
vidscope brief clip.mp4 --target 21 34
```

Run `probe` first. It is free and it tells you which frames are worth spending
a vision call on.

## Measured accuracy

These are measured against ground truth, not estimated. A number without its
denominator does not appear in this project.

| Measurement | Result | Method |
|---|---|---|
| Cut precision | 91/91 | 20 real stock clips, each cut checked against frame difference |
| Cut recall | 30/30 | Cuts constructed by splicing, so ground truth is arithmetic |
| Black detection | 0 mismatches / 20 | Scored against raw `blackdetect` output |
| Freeze detection | 0 mismatches / 20 | Scored against raw `freezedetect` output |

**Not proven:** dissolves, wipes and fades are not detected. No 4K, HDR,
10-bit, VFR or long-form footage has been tested. A cut immediately followed by
a byte-identical duplicate frame scores 0.000 in `scdet` and goes unreported.

Full method: `docs/cut-detection-accuracy.md` in the repository.

## Permissions

Declared honestly, because a scanner rewards transparency and so does a buyer:

- **Read files.** Reads the video file you point it at, and nothing else.
- **Write files.** Writes only the contact sheet image and its JSON sidecar to
  the path you pass via `--out`, or to a fresh temporary directory it creates
  and reports. Never touches your project files.
- **Terminal / shell.** Invokes `ffmpeg` and `ffprobe` with argument lists. It
  does not use a shell, so there is no command string to inject into.
- **Network access.** None. There is no HTTP client, no socket, no telemetry,
  and no download step in this skill. The package contains zero URLs of any
  kind, so there is nothing to point at an endpoint.
- **Environment variables.** None are read. No credentials are needed, so none
  are stored or harvested.

## What it does not do

- It does not edit or cut video. It measures; something else cuts.
- It does not transcribe audio. It reports the audio stream count only.
- It does not decide whether a clip is good. It reports what is measurable and
  says what it did not check.

## Honest limits

A contact sheet at 330 pixels is triage, never verification. It cannot be used
to confirm a label, a watermark or a brand. Every text finding has to be
escalated to a full resolution frame at that exact timestamp before it changes
what you do. The skill documents this at length, because a confident wrong
answer about on-screen text is the most expensive mistake this tool can make.

## Licence

MIT.
