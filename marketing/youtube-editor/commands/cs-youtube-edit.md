---
name: "cs-youtube-edit"
description: "/cs-youtube-edit — Edit a raw recording into an upload-ready YouTube video: measure, propose cuts (silence, fillers, retakes), get approval, add transitions and effects if asked, plan to the frame, render H.264/AAC at −14 LUFS, and verify every cut, transition and effect against the source before delivery."
argument-hint: "[path to the raw video] [optional: words.json, chapters.txt, 'shorts']"
---

# /cs-youtube-edit — Precision edit, verified

**Command:** `/cs-youtube-edit raw.mp4 [words.json] [chapters.txt] [shorts]`

Runs the `cs-youtube-video-editor` loop from [`../skills/youtube-editor/SKILL.md`](../skills/youtube-editor/SKILL.md).

## When to run

- "Edit this recording for YouTube" / "cut the dead air and the ums"
- "Apply this cut list exactly" / "make a Short from 3:10 to 4:40"
- "Fix the chapters after I cut the intro"
- "Add a crossfade between sections, zoom in at 2:10, burn captions for the Short"

## When NOT to run

- Downloading or transcribing a *published* video → `youtube-full`
- Only checking an existing render → [`/cs-youtube-verify`](cs-youtube-verify.md)

## Steps

1. Forcing questions, one per turn (purpose, pacing, word timestamps, must-keep moments, preset).
2. `media_analyzer.py probe` + `analyze` — report warnings.
3. `media_analyzer.py propose --edl-out edl.json` + editorial cuts from the transcript → cut table → **approval**.
4. Transitions/effects into the EDL only if asked (`effects_library.py list`), then
   `edit_planner.py edl.json --snap-words --plan-out plan.json` → resolve findings.
5. `render_engine.py plan.json -o final.mp4` (draft preview first for long videos).
6. `edit_verifier.py plan.json final.mp4` → PASS required; ≤ 3 fix rounds.
7. `timeline_remapper.py chapters …` and `captions … --words …` when supplied.

## What you get

- `final.mp4` — frame-exact, H.264 High / AAC 48 kHz / −14 LUFS / faststart.
- The verifier report: frame count, per-cut frame match, audio alignment, loudness, upload spec.
- A description-ready chapter block and an `.srt`, both remapped through the edit.
