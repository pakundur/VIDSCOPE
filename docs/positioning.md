# Positioning

How VidScope is presented, why, and what it deliberately does not claim.

GitHub's default repository search matches **only the name, description and
topics**. README text is not searched unless a user adds `in:readme`, which
almost nobody does. So positioning lives in three short fields, and the README
does the second job: converting a visitor who already clicked.

Both are specified here so the wording stays consistent across GitHub, the
listing, the skill file and any launch post.

---

## The one-sentence position

> Video forensics a script can trust: cuts, black, freeze and luma in one JSON
> call, with every claim measured and every limit documented.

Use this verbatim in the GitHub About field, the social preview, and the first
line of any listing.

---

## The three claims, in priority order

**1. The evidence is measured, and the limits are published.**

Every number traces to a method: 91/91 cut precision on 20 real clips, 30/30
recall on constructed cuts, 0/20 mismatches on black and freeze, luma within
0.06. The accuracy doc also names what was never tested: no 4K, HDR, VFR or
long-form, no dissolves, wipes or fades. It also records one genuine ffmpeg
limitation found during the work.

Almost nothing else in this category publishes an accuracy figure at all. This
is the differentiator, so it appears above the fold.

**2. It runs where nothing else will.**

Standard library plus `ffmpeg`. No pip, venv, API key, Docker or Node. Measured
on a phone in Termux. That is a real constraint that eliminates most of the
category.

**3. One call returns one object.**

Duration, cuts, black, freeze, luma and actionable flags arrive together as
JSON. Competitors split this across separate commands, GUI tools or log parsing.

Convenient, not unique. Ranked third on purpose.

---

## What is deliberately conceded

Honesty here is a feature, not a liability. A reviewer who knows the space will
test these claims, so they are conceded first, in the README, in writing:

- **PySceneDetect is better at scene detection.** BSD-3, active since 2014,
  multiple detectors, splitting, image export, Python API, Docker. VidScope
  wraps one ffmpeg filter and a hand-tuned threshold. If detection quality is
  the problem, use PySceneDetect. The README says so explicitly.
- **The agent-video space is crowded.** `claude-real-video`, `agentic-video`,
  `popcorn`, `watch-video` and others already do frame sampling, transcription
  and contact sheets, mostly with more features. VidScope is not competing
  there.
- **"Zero dependencies" is not unique.** At least one competitor states the
  same design goal. It is a reason VidScope exists, not a claim of novelty.
- **Cut detection has a measured blind spot.** A cut immediately followed by a
  byte-identical duplicate frame scores 0.000 and goes unreported. Reproduced
  with frame-level data, documented, not hidden.

---

## GitHub fields

**Repository name:** `VIDSCOPE` (identifier; the description carries the search
terms, the name does not need to).

**About description** (paste verbatim, one line):

```
Video forensics a script can trust: cuts, black, freeze and luma in one JSON call. Every claim measured, limits documented.
```

**Topics** (all 20; GitHub allows 20 and most repos use 4, so this is free
ranking surface). Lowercase, hyphens, under 50 characters each:

```
video
ffmpeg
ffprobe
video-analysis
scene-detection
shot-detection
cut-detection
blackdetect
freezedetect
scdet
video-forensics
video-quality
contact-sheet
cli
python
no-dependencies
json
agent-skill
benchmark
quality-assurance
```

Rationale for the less obvious ones:

- `blackdetect`, `freezedetect`, `scdet`: exact ffmpeg filter names people
  search when a filter is misbehaving. High intent, low competition.
- `benchmark` and `quality-assurance`: reach the audience that cares about
  measurement, which is the target reader.
- `video-forensics` and `video-quality`: the domain an editor or QA engineer
  would browse, as opposed to `video-analysis`, which is saturated.
- `agent-skill`: matches how the package is also distributed.

**Website field:** leave empty until a docs site exists. A dead link is worse
than no link.

**Social preview:** 1280×640 PNG, under 1 MB. Name, the one-sentence position,
and a real terminal frame showing the probe JSON with the `FROZEN` and `LOW-RES`
flags visible. Not a logo. The output is the product.

---

## README order, and why

1. **Title plus one-sentence position.** A visitor decides in seconds.
2. **Real terminal output.** Actual measured JSON from a real clip, not a
   mockup. Proof before prose.
3. **Accuracy table.** Leads with results because that is the differentiator.
4. **Limits paragraph.** Immediately after the numbers, so the numbers cannot
   be read as overclaiming.
5. **"What this is, and what it is not."** Concessions up front, competitor
   links included.
6. Install and quickstart.
7. Command reference.
8. Security, limits, tested-on, layout, tests, contributing, license.

Badges are deliberately minimal. No star-count badge, no "awesome" badge. The
build-status and licence badges do a real job; the rest is noise.

---

## Voice rules

Applied to the README, the accuracy doc, the listing and any launch post:

- **No em dashes in prose.** Only inside literal quoted program output, where
  the dash is part of the tool's own string.
- **No AI tells.** No "Naturally", no "Discover", no colon-led feature lists, no
  repeated identical sentence openers.
- **No unqualified superlatives.** "Finds hard cuts reliably, with measured
  precision and recall" is accurate. "Finds every scene boundary" is not, and
  dissolves are untested.
- **Numbers carry their method.** A figure without a denominator and a source
  does not appear.
- **Retractions stay visible.** Where a claim was once wrong and later
  corrected, the correction is recorded rather than quietly edited out. The
  `scdet` parameter explanation in the accuracy doc is wrong twice on purpose,
  as a record of the process.

---

## What would make this position false

Recorded so it can be checked rather than assumed:

- If cut precision or recall drops below the published figures on new footage,
  the table must change, not the wording.
- If a 4K, HDR or long-form test is run and fails, the "not proven" section
  becomes a "known failure" section.
- If PySceneDetect ships measured recall that beats 30/30 on the same
  constructed method, that concession gets stronger, not weaker.

The position is only worth anything while it survives being tested.
