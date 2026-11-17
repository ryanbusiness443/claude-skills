---
name: "cs-reels-edit"
description: "/cs-reels-edit — Turn a raw talking-head clip into a retention-edited Short, Reel or TikTok: hook title card, jump cuts, zoom rhythm, punch-ins on key words, karaoke captions, synthesized sound effects and shocks, progress bar and a loop ending, planned from the transcript, rendered frame-exact, verified, and scored 0-100 for retention."
argument-hint: "[raw clip] [optional: clean|punchy|insane, music file, hook text]"
---

# /cs-reels-edit — Short-form edit, planned like an editor, proven like an engineer

**Command:** `/cs-reels-edit raw.mp4 [punchy] [bed.mp3] ["HOOK TEXT"]`

Runs the reels mode of [`../skills/youtube-editor/SKILL.md`](../skills/youtube-editor/SKILL.md).

## When to run

- "Make this a viral reel" / "edit this for TikTok, Shorts or Reels"
- "Add the captions, zooms and sound effects everyone uses"
- "Why do people swipe away from my videos?" (audit an existing plan)

## When NOT to run

- Long-form editing with a hand-approved cut list → [`/cs-youtube-edit`](cs-youtube-edit.md)
- Only checking a render → [`/cs-youtube-verify`](cs-youtube-verify.md)

## Steps

1. Ask the intensity (recommend **punchy**; **insane** only for hype or entertainment), the hook
   (recommend the payoff, not a greeting), and whether a licensed music bed is available.
2. Transcribe with word timestamps (faster-whisper) if no transcript exists.
3. `viral_planner.py raw.mp4 --words words.json --intensity punchy --music bed.mp3
   --edl-out reel.edl.json --notes-out notes.md`. Read the editor's notes back to the user.
4. `edit_planner.py reel.edl.json --snap-words --plan-out reel.plan.json` → resolve findings.
5. `render_engine.py reel.plan.json -o reel.mp4`, then `edit_verifier.py reel.plan.json reel.mp4`
   → PASS required, at most 3 fix rounds.
6. `retention_audit.py reel.plan.json --format short` → apply the fixes it lists, then re-plan.
7. Look at a contact sheet of the render before delivering: the checker proves the render matches
   the plan, not that the plan looks good.

## What you get

- A vertical 1080×1920 MP4 at −14 LUFS with every cut, effect and sound effect verified.
- The editor's notes: each decision with its timestamp and reason.
- A retention score with the fixes that would raise it, plus the honest caveat: the edit keeps
  people watching, but the idea and the first sentence decide whether it spreads.
