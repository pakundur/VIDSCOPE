# Changelog

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
