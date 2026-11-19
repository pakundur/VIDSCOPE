# Showing this to someone

Copy-paste material for a launch post, a CV line, or a listing. Keep the numbers
attached to their method, and keep the concessions in.

---

## Show HN draft

**Title**

```
Show HN: I measured my video cut detector instead of guessing
```

**Body**

```
I built a small ffmpeg wrapper that reports what is technically wrong with a
video file: where the cuts are, black intervals, frozen frames, luma stats, and
flags written as actions rather than trivia. Output is one JSON object.

The tool is not the interesting part. PySceneDetect does detection better and
has for years, so if that is your problem you should use it.

What I could not find anywhere in this category was a published accuracy
figure. So I measured mine two ways.

Precision: 91 reported cuts across 20 real stock clips, each one checked frame
by frame against the actual pixel difference. 91/91 landed on a real
discontinuity.

Recall: you cannot measure recall against footage where you guessed the cut
list, so I constructed it. Mine single-shot segments from the corpus (a segment
between two known cuts is continuous by construction), concatenate them, and
the cut count is arithmetic. 30 constructed cuts, 30 found, 0 false positives.

Two things went wrong on the way there, both worth mentioning:

The first recall run reported 91.7% with two misses. Investigating instead of
filing it as a tool defect showed my own normalisation step had produced a
duplicate frame at the splice. That led to a real ffmpeg finding: scdet scores
each frame against its predecessor, so a cut followed by a byte-identical
duplicate scores 0.000 and is invisible. Reproduced with frame-level data.

I also got the scdet parameters wrong twice in writing before checking
`ffmpeg -h filter=scdet`, and the wrong version was committed to the docs. Both
corrections are still in there.

Scope, stated plainly: everything tested was short portrait social video. No
4K, HDR, 10-bit, VFR or long-form. Recall was measured on hard cuts only.
Dissolves, wipes and fades are not detected and I do not claim them.

It runs on stdlib plus ffmpeg with nothing to install, which is why it works on
a phone in Termux, where most of this category does not run at all.

Repo: <link>
Accuracy doc: <link>
```

---

## CV line

> Built and measured VidScope, a dependency-free video forensics CLI (MIT).
> Established ground truth by splicing cuts at known timestamps rather than
> inferring them from scores, reaching 91/91 cut precision and 30/30 recall.
> Found and documented a genuine `scdet` duplicate-frame limitation, and
> corrected two wrong parameter descriptions in the project's own docs after
> verifying against `ffmpeg -h`.

The second half matters more than the first. Anyone can report a percentage.
Few candidates can show they retracted their own published claim when testing
disproved it.

---

## Talking points if asked

**"How is this different from PySceneDetect?"**
It is not different in kind, and it is narrower. PySceneDetect has multiple
detectors, splitting, export and years of history. VidScope does one detection
path plus black, freeze and luma in a single JSON call with no install, and it
publishes its measured accuracy and its untested cases. If you want the better
detector, take PySceneDetect.

**"Aren't there dozens of agent video skills?"**
Yes, and most are more capable. VidScope is not competing on features. It is
positioned on measurement discipline and on running in environments where you
cannot install a Python package.

**"What did you actually learn?"**
That a test never seen to fail is not evidence. The first version of the
adversarial suite passed 22/22 against code with three known bugs in it, because
two assertions only checked the exit code. That is now a rule in the project:
every check asserts a behaviour, and the suite has been run against deliberately
reintroduced bugs to confirm it can fail.

**"What is the tool bad at?"**
Dissolves, wipes and fades, which it does not detect. Cut detection adjacent to
a duplicated frame, which silently disappears. Anything above 1080p, which is
untested. Measured product claims from a downscaled frame, which it is built to
refuse.

---

## What not to say

- Not "finds every scene boundary." Dissolves and fades are untested.
- Not "better than PySceneDetect." It is not, and reviewers test that first.
- Not "unlike other tools, zero dependencies." Others say the same.
- Not "AI-powered." There is no model in it, by design.
- No accuracy figure without its denominator and its method.
