---
name: "youtube-editor"
description: "Frame-accurate YouTube video editing agent: cuts silences, filler words and retakes, renders an upload-ready MP4, and proves every cut landed on the exact frame before calling it done. Use when the user wants a raw recording edited for YouTube, dead air or 'um's removed, a cut list applied precisely, a Shorts version, chapters or captions carried through an edit, or a render checked against YouTube's upload spec. Do NOT use for downloading YouTube videos, thumbnail design, or generating new footage."
license: "MIT"
---

# youtube-editor — precision editing, verified

The agent decides *what* to cut; five stdlib tools on top of ffmpeg decide *where*, to the frame and the audio sample, and then prove it. Nothing is reported as done until `edit_verifier.py` returns PASS.

**Requires** ffmpeg ≥ 5.1 (`brew install ffmpeg` / `sudo apt install ffmpeg`). Word timestamps are optional but unlock word-safe cuts and filler removal: `pip install faster-whisper`, or reuse an existing transcript JSON. Never install anything without asking.

## Workflow (bounded loop)

1. **Interview** — ask the forcing questions below, one at a time, each with a recommended answer.
2. **Measure** — `python3 scripts/media_analyzer.py probe raw.mp4`, then `analyze`. Read the warnings (VFR, interlaced, A/V offset) aloud to the user.
3. **Propose** — `media_analyzer.py propose raw.mp4 --words words.json --edl-out edl.json`. Show the cut list; the user approves or edits it. Proposals are never applied unread.
4. **Plan** — `python3 scripts/edit_planner.py edl.json --snap-words --plan-out plan.json`. Exit 3 (BLOCKED) → fix the EDL and re-plan. Exit 2 → resolve or explicitly accept each warning.
5. **Preview** — `python3 scripts/render_engine.py plan.json -o preview.mp4 --preset draft`, verify it, let the user watch.
6. **Render** — `render_engine.py plan.json -o final.mp4` (never over the source; never stream-copy).
7. **Verify** — `python3 scripts/edit_verifier.py plan.json final.mp4`. FAIL → diagnose with `references/edit_decision_playbook.md` §4, fix, re-render. **Max 3 render→verify rounds**, then stop and escalate with the report.
8. **Carry over** — `python3 scripts/timeline_remapper.py chapters plan.json chapters.txt` and `captions plan.json --words words.json -o final.srt`.

```bash
# The whole loop on a self-made test clip, no input needed:
python3 scripts/edit_verifier.py --sample     # renders, verifies, and runs a negative control
```

## Forcing-question library

Ask one per turn, recommend an answer, cite the reason.

1. **What is the finished video for?** Long-form, Short, or both. *Recommend:* long-form first; a Short is a re-plan of the same EDL with `--preset youtube-shorts` (≤ 3 min, 9:16).
2. **How tight should pacing be?** *Recommend:* 0.15 s padding at each cut; 0.25 s for teaching content where viewers need a beat (playbook §1).
3. **Do you have word timestamps?** *Recommend:* yes — without them the planner cannot see a cut that clips a word.
4. **Which moments must survive?** Deliberate pauses, punchlines, b-roll windows. They become explicit keeps, never silence-detected cuts.
5. **Where does the output go?** *Recommend:* `youtube` preset at native resolution; upscale to 4K only when asked.

## Precision guarantees (each one is checked, not assumed)

| Guarantee | Enforced by |
|---|---|
| Cuts land on real frame boundaries; times are exact rationals (29.97 = 30000/1001) | `edit_planner.py` |
| No cut lands inside a spoken word (with `--words`) | planner `MID_WORD` / `--snap-words` |
| Audio boundaries derive from the output frame timeline: zero cumulative drift | planner sample math |
| Output frame count equals the plan, exactly | verifier `FRAME_COUNT` |
| The frame after every cut is the intended source frame (offset 0 of ±2) | verifier `CUT_FRAMES` |
| Integrated loudness −14 LUFS ±1, true peak ≤ −1 dBTP | renderer two-pass loudnorm + verifier |
| H.264 High / yuv420p / AAC 48 kHz / faststart / closed GOP | renderer + verifier `UPLOAD_SPEC` |

## Hard rules

- Never overwrite or modify the source. Never use `-c copy` for a cut: it snaps to keyframes.
- Never declare an edit finished without a PASS report; show the report.
- Never apply proposed cuts the user has not seen. Never cut inside a word to save a frame.
- Verifier says AMBIGUOUS on static shots: report it honestly; it is not a PASS on that boundary.

## Tools

| Script | Job | Exit codes |
|---|---|---|
| `media_analyzer.py` | probe · analyze (silence, black, scenes, loudness) · propose EDL | 0 · 1 none · 4 · 6 |
| `edit_planner.py` | EDL → frame/sample-exact plan with findings | 0 · 2 warn · 3 blocked |
| `render_engine.py` | plan → MP4 in one decode pass | 0 · 1 · 3 · 4 · 6 |
| `edit_verifier.py` | plan + render → PASS/FAIL with per-cut frame matching | 0 pass · 1 fail |
| `timeline_remapper.py` | chapters · captions · timestamps through the edit | 0 · 2 warn |

All support `--help`, `--sample` and `--output json`. Schemas and edge cases: `references/precision_editing_canon.md`, `references/youtube_delivery_spec.md`, `references/edit_decision_playbook.md`. Templates: `assets/`.
