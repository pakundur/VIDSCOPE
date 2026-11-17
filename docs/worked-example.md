# Worked example — one clip, three rungs, one real finding

A complete run on a real file, showing what each rung actually buys you.
Use this as the template for how deep to go.

---

## The clip

`k01.mp4` — 16.10s, 720×1280 portrait, 30fps, h264, 1 audio stream, 3.3 MB.
A yellow multi-function jar/bottle opener being demonstrated.

## Rung 0 — signal pass (free, ~2s)

```bash
vidscope probe k01.mp4
```

```
k01.mp4
  16.10s @ 30.0fps  720x1280 (portrait)  3.3 MB  h264
  audio streams: 1   scene cuts: 7
  FLAGS:
    ! SUB-HD — 720x1280; usable but below the 1080x1920 native standard
```

**What this told us before spending anything:**

- 7 cuts / 16.1s = **26 cuts/min** → fast demo montage, ~2.3s per shot.
  Each shot is a different function. Not one continuous take.
- Audio present → no need to add music.
- No black, no freeze, no exposure fault → nothing broken. Skip the defect hunt.
- Portrait, near-9:16 → no crop needed. But 720×1280 is sub-HD, so upscaling to
  1080×1920 will soften it slightly. Worth knowing before it sits next to
  native clips in the same feed.

Decision: worth a vision call. If flags had shown `FROZEN` or `DARK`, we would
have fixed that first rather than spending a call describing unusable footage.

## Rung 1 — 330px overview (one vision call)

```bash
vidscope sheet k01.mp4 --rung 1
```

→ 4×4 sheet, 1 frame/sec.

Vision read: *"yellow, triangular multi-function jar and bottle opener"* —
opening a stubborn jar lid, magnetic lid lift, bottle cap pry, pull-tab can.
Before/problem state: sealed crusty jar. Payoff: opened can.

Also reported: **"some text on the jar labels (e.g. 老干妈)"**.

**At 330px that text claim is a lead, not a finding.** We cannot read 老干妈 at
330px — so either the model invented it (it has invented "TEA", "GRAND",
"HOME", "ON", "FASHION", and an entire "Adidas logo" on other clips) or it is
real and disqualifying. We do not know yet. Escalate.

## Rung 3 — 1080px confirmation

```bash
vidscope sheet k01.mp4 --rung 3 --times 0.0 0.5 1.0 1.5
```

→ 2×2 at full resolution. Forced-choice question, with "no text" offered as an
explicit option.

Result: **CONFIRMED REAL.** 老干妈 (Lao Gan Ma) legible on the lid, plus `280g`
and printed dates `2025/08/26`, `2024/02/25`.

This clip is **not usable** for affiliate or sponsored content — third-party
brand, readable, on-screen. The decision was correct *only* because it was
verified; a 330px guess in either direction would have been a coin flip.

## The two failure modes this example demonstrates

**Failure mode 1 — trust the sheet, ship a brand.** The 330px sheet said "some
text." Shipping on that would have published Lao Gan Ma. The sheet was right
this time; on five other clips the sheet invented text that did not exist.
Both directions of error are real, so the sheet can never be the deciding vote.

**Failure mode 2 — stop at 330px and reject good clips.** The reverse costs you
usable content. On the same batch, vision reported "HOME" text on a steel-wool
clip and an "Adidas three-stripe logo" on a shoe clip. Full-resolution zooms
showed **neither existed** — a pot rim and colour-blocking. Rejecting those on
the sheet's word would have thrown away clean clips.

## Cost of getting it right

| Step | Time | Cost |
|---|---|---|
| rung 0 probe | ~2s | free |
| rung 1 sheet + read | ~10s | 1 vision call |
| rung 3 confirm | ~15s | 1 vision call |

**~30s and 2 vision calls per clip** to go from "file" to "verified usable or
verified rejected." Compare that with publishing an undisclosed brand and
eating the reach penalty on every post after it.

## Rule extracted

> The sheet tells you **where to look**. Only full resolution tells you
> **what is there**. Never let a downscaled frame make a decision that a
> full-resolution frame could overturn.
