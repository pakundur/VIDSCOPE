# Repository metadata: apply these in the GitHub web UI

GitHub's default search indexes **only the name, description and topics**.
README prose is not searched unless a user adds `in:readme`. These three fields
are therefore the highest-value text in the project, and they take two
minutes to set.

Settings → the gear icon beside **About** on the repository main page.

---

## Description

Paste verbatim into the About description field:

```
Video forensics a script can trust: cuts, black, freeze and luma in one JSON call. Every claim measured, limits documented.
```

## Topics

Paste one at a time. GitHub accepts up to 20; all 20 are used here.

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

## Website

Leave empty until a docs site exists. A dead link is worse than no link.

## Social preview

Settings → General → Social preview. 1280×640 PNG or JPG, under 1 MB.

Content: the project name, the one-sentence position, and a real terminal frame
showing `vidscope probe --json` output with the `FROZEN` and `LOW-RES` flags
visible. The product is the output, so the preview should show output. Not a
logo, not an abstract graphic.

---

## Why these topics

| Topic | Reason |
|---|---|
| `blackdetect` `freezedetect` `scdet` | Exact ffmpeg filter names people search when a filter misbehaves. High intent, low competition. |
| `benchmark` `quality-assurance` | Reach the reader who cares about measurement, which is the target audience. |
| `video-forensics` `video-quality` | Domain terms an editor or QA engineer browses. Less saturated than `video-analysis`. |
| `agent-skill` | Matches how the package is also distributed. |
| `no-dependencies` `json` `cli` | How someone restricts a search when they cannot install packages. |

Most repositories carry four or five topics and leave the rest unused. Each
topic is a separate exact-match surface on a page developers actively browse,
so leaving 15 unclaimed is a self-inflicted discovery problem.

---

## Releases

Tag releases with short notes. A repository with a `1.0.0` tag and a changelog
signals it is maintained; one with 40 commits and no tag reads as a scratch
project, fairly or not.

```bash
git tag -a v1.0.0 -m "1.0.0 — measured cut detection, black/freeze/luma, agent skill"
git push origin v1.0.0
```

Then create the Release object in the web UI with the CHANGELOG section for
that version as the body.
