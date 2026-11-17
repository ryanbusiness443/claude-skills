---
name: "cs-montage-edit"
description: "/cs-montage-edit — Cut a folder of clips to a music track with every cut on the beat: day-in-my-life vlogs, motivation montages, story sequences, recaps. Detects tempo, beats, downbeats and rises, joins the clips frame-exact, applies the genre's grade, texture, time cards, quotes and hits, renders, and proves each cut landed within half a frame of its beat."
argument-hint: "[clips folder] [music file] [day-in-life|motivation|storytelling]"
---

# /cs-montage-edit — B-roll cut to the music, proven on the beat

**Command:** `/cs-montage-edit clips/ track.mp3 day-in-life`

Runs the montage mode of [`../skills/youtube-editor/SKILL.md`](../skills/youtube-editor/SKILL.md).

## When to run

- "Make a day in my life from these clips" / "cut this B-roll to the beat"
- "Motivation edit with this song" / "a recap of the event, synced to music"

## When NOT to run

- Someone talking to camera → [`/cs-reels-edit`](cs-reels-edit.md) (add `--beat-sync` there)
- Only checking a render → [`/cs-youtube-verify`](cs-youtube-verify.md)

## Steps

1. Ask the genre (recommend **day-in-life** for vlogs, **motivation** for hype, **storytelling**
   for anything with a turn), the format (recommend **short**, 9:16), and the music. No licensed
   track? Recommend `asset_packs.py pack --style <genre>`: CC0 OpenFilm music and sounds.
2. Large clips: bring them in through Google Drive or a direct link, never re-encoded
   (`../skills/youtube-editor/references/workspace_and_inputs.md`).
3. `beat_detector.py track.mp3` → read the tempo and confidence back. Below 0.3, or if it
   sounds wrong, pass `--bpm`.
4. `montage_planner.py clips/ --music track.mp3 --style day-in-life --labels "7 AM,9 AM,..."
   --bound-out bound.mp4 --edl-out m.edl.json --notes-out notes.md [--pack pack.json]`.
5. `edit_planner.py m.edl.json --plan-out m.plan.json`, `render_engine.py m.plan.json -o m.mp4`,
   `edit_verifier.py m.plan.json m.mp4` → PASS with `BEAT_SYNC`, at most 3 fix rounds.
6. Look at a contact sheet before delivering: the checker proves the cuts are on the beat, not
   that the shots tell the day well.

## What you get

- An MP4 at −14 LUFS with every cut within half a frame of its beat, the music verified in place,
  and every effect checked on its frames.
- The editor's notes: tempo, shots, reused footage (if any), and why each move was made.
