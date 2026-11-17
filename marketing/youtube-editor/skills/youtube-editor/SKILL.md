---
name: "youtube-editor"
description: "Frame-accurate video editing agent for YouTube and short-form reels: cuts silences, filler words and retakes; auto-plans retention edits (hook title card, jump cuts, zoom rhythm, punch-ins, karaoke captions, synthesized sound effects, flash/shake/glitch shocks, progress bar, loop ending) and scores them; adds 50+ transitions and effects; renders upload-ready MP4s and proves every cut, effect and sound landed on the exact frame. Use when the user wants a raw recording edited for YouTube, Shorts, Reels or TikTok, a video made more engaging or viral, dead air or 'um's removed, transitions, effects or captions added, or a render checked against the upload spec. Do NOT use for downloading YouTube videos, thumbnail design, or generating new footage."
license: "MIT"
---

# youtube-editor — precision editing, verified

The agent decides *what* to cut; stdlib tools on top of ffmpeg decide *where*, to the frame and the audio sample, and then prove it. Nothing is reported as done until `edit_verifier.py` returns PASS.

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

## Transitions and effects

Add them in the EDL; `python3 scripts/effects_library.py list` shows every option and `check edl.json` validates a file.

```json
"transition": {"type": "fade", "duration": 0.4},
"effects": [{"type": "zoom", "start": "1:02.5", "end": "1:06", "scale": 1.2},
            {"type": "text", "start": "0:03", "end": "0:07", "text": "Step 1", "position": "top"},
            {"type": "captions", "source": "words.json", "style": "shorts"},
            {"type": "music", "file": "bed.mp3", "volume_db": -18, "duck": true}]
```

A per-cut `"transition"` overrides the default. Local effects (`zoom`, `text`, `blur`) take **source** times, so they move with the content when cuts change. Transitions overlap pieces, and the planner shortens the timeline by exactly that many frames, video and audio. Ask before adding effects the user did not request: restraint is part of the craft.

## Reels and viral mode

For Shorts, Reels and TikTok, let the planner make the short-form editor's calls, then run the normal plan → render → verify loop and score the result:

```bash
python3 scripts/viral_planner.py raw.mp4 --words words.json --intensity punchy --music bed.mp3 \
    --edl-out reel.edl.json --notes-out notes.md          # clean | punchy | insane
python3 scripts/retention_audit.py plan.json --format short   # 0-100, fixes listed
```

It cuts every pause, puts the first word on frame 1 under a hook title card with a flash and boom, alternates framing so the frame never sits still past 1.6–4 s, punches in on numbers and power words, frames the call to action tightest, and ends hard so the replay loops. Shocks (`flash`, `shake`, `glitch`, `bw`) and synthesized `sfx` are punctuation, capped by density. Match intensity to content: `insane` on a serious topic reads as noise. Read the notes back to the user, and say plainly that the edit raises retention, not the idea's appeal (`references/short_form_retention.md`).

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
| Each effect is on at its first and last frame and off just outside (zoom, text, blur) | verifier `EFFECTS` |
| Transitions match a rebuild; captions and sound effects land at the right time | verifier `TRANSITIONS`, `CAPTIONS`, `SFX_ALIGN`, `FADES` |

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
| `effects_library.py` | list transitions/effects/sounds · validate an EDL's effects | 0 · 2 · 3 |
| `viral_planner.py` | transcript → retention EDL + editor's notes | 0 · 4 · 6 |
| `retention_audit.py` | plan → retention score 0-100 with fixes | 0 · 2 below 75 |

All support `--help`, `--sample` and `--output json`. Schemas and edge cases: `references/precision_editing_canon.md`, `references/youtube_delivery_spec.md`, `references/edit_decision_playbook.md`, `references/effects_and_transitions.md`, `references/short_form_retention.md`. Templates: `assets/`.
