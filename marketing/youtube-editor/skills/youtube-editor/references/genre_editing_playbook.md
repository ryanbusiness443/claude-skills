# Genre editing playbook: storytelling, motivation, day in my life

How each genre is edited, why, and which flags make the tools do it. The style changes what the
edit is *for*; intensity only changes how fast it moves. 🟢 primary source or platform
documentation · 🟡 widely reproduced editor practice or third-party measurement · 🔴 folklore,
named so it is not repeated as fact.

## 1. The three questions every genre answers differently

| Question | Storytelling | Motivation | Day in my life |
|---|---|---|---|
| What carries the viewer? | Tension: will it resolve? | Energy: the music and the line | Curiosity and company: what happens next |
| What does a cut do? | Moves the story to its next beat | Hits with the music | Moves the clock forward |
| What does sound do? | Builds and releases tension | Drives everything | Sets the mood, ticks the time |
| Default pace | 4 beats a shot, `clean` jump cuts | 2 beats a shot, 1 in rises | 2 beats a shot |
| Grade | `moody` (lifted blacks, low sat) | `teal-orange` (warm skin, teal shadows) | `warm-vlog` (soft, sunny) |
| Texture | grain 8, vignette 0.45 | grain 6, vignette 0.35, bars on landscape | grain 3, vignette 0.2 |

🟡 Murch's "rule of six" ranks emotion first and rhythm third among reasons for a cut. Each
genre above weights them differently, which is why one preset cannot serve all three.

## 2. Storytelling

**Structure.** Hook with the conflict, not the background ("I lost everything in a week" beats
"So, back in 2019..."). Then setup, a turn, an escalation and a payoff. 🟡 The turn is where people
stay or leave: put the sound design there.

**What the planner does** (`viral_planner.py --style storytelling`):
- Pacing drops to `clean`: pauses under 0.40 s stay, because silence is part of the delivery.
- Every sentence that opens with a turn word (*but, then, until, suddenly, so, except, however,
  instead*) gets a **riser that ends on the turn** (placed in output time, so cuts cannot shift
  it), a hit on the turn word, and a slow 1.12× push-in for the sentence. At most three turns: a
  story with ten turns has none.
- No turn word found → the notes say so and ask you to name the turn with `--emphasis`.

**For B-roll stories** (`montage_planner.py --style storytelling`): 4 beats a shot (a bar at
4/4), push-ins on alternate shots, lines as lower-third text, and a 1 s fade out.

**Rules of thumb.** 🟡 Hold on the reaction, not the action. 🟡 Let music drop out right before
the payoff, because silence is the loudest sound. 🟡 Never put a flash or glitch in a sad story.

## 3. Motivation

**Structure.** One idea, a cold open on the strongest line, rising energy, a final line that
lands on the drop. 🟡 Motivation edits live or die on the music: choose the track first and cut
to it.

**What the tools do:**
- `viral_planner.py --style motivation`: teal-orange grade, grain and vignette, and the line with
  the most power words as a **centre quote card with an impact**. On landscape it adds 2.0:1
  cinematic bars. With `--beat-sync`, jump cuts slide inside their pauses onto the beat, and
  punches and hits move onto the nearest beat within 120 ms.
- `montage_planner.py --style motivation`: shots of 2 beats, 1 beat once the music **rises**
  (from `beat_detector.py` sections). Flashes and impacts land on downbeat cuts in the rise, with
  a shake on the first big hit, and `--text` lines appear as centre quotes on downbeats.

**Rules of thumb.** 🟡 Speed comes from the cut rate, not from effects: two effects per shot is
noise. 🟡 Black-and-white is a punctuation mark: one or two moments. 🔴 "Motivation edits need a
speech from a famous person." Using someone else's speech without a licence gets the video muted
or taken down; record your own voice-over.

## 4. Day in my life

**Structure.** A clock: morning to night, in order. 🟡 The first shot is the most interesting
moment of the day, not the alarm clock. Show it first as a hook, then rewind to morning.

**What the tools do:**
- `montage_planner.py --style day-in-life`: clips stay in **your order** (chronological). Each
  clip's first shot gets a **time card**, taken from `--labels` or from the camera's recorded
  clock (`creation_time`). A shutter click marks each new moment, with 2 beats a shot, a warm
  grade and light grain.
- `viral_planner.py --style day-in-life` (a voice-over day): sequence words (*first, then, next,
  later, finally, morning, lunch...*) get a shutter click.

**Rules of thumb.** 🟡 Natural sound under the music (`--ambient-db -30`, the default) makes it
feel lived-in: the coffee pour, the door, the keyboard. 🟡 1–2 s per shot is the vlog sweet spot.
Below 0.5 s it becomes a trailer, above 3 s it becomes a documentary.

## 5. Cutting to the beat

**How the beat is found** (`beat_detector.py`, stdlib plus ffmpeg):
1. ffmpeg splits the track into three bands: kick < 150 Hz, body 150–4000 Hz, air > 4000 Hz.
2. Rises in log energy, summed over the bands, give an onset envelope at ~100 Hz.
3. Autocorrelation under a 120 BPM prior gives the tempo (🟢 Ellis 2007's tracker uses the same
   prior). Then a **metre re-rank** tests ×½, ×⅔, ×¾, ×4/3, ×3/2 and ×2 by how strongly each
   grid lands on onsets.
4. Dynamic-programming tracking picks the beats (🟢 Ellis 2007).
5. Each beat is refined between hops, and downbeats are the beat phase with the most kick energy.

**Measured, not claimed:**

| Test | Result |
|---|---|
| Synthetic 120 BPM click track | worst beat error 4.4 ms, downbeats correct |
| 10 random OpenFilm library tracks vs their catalogue BPM | 5 equal; in 4 of the other 5 the detected grid lands on onsets more strongly than the catalogue's |
| Montage render, 9 cuts | 9/9 on the beat (worst 4.4 ms, under half a frame); music in place to 0.1 ms |
| Negative controls | beats shifted 2 frames → FAIL; music 2 frames late → FAIL (+68 ms) |

A catalogue tempo is not ground truth. When the detector and the listing disagree, the output
lists both with their grid fit; trust your ear, then pass `--bpm`.

**What "on the beat" means here.** A cut lands on the frame nearest its beat, so the worst
offset is half a frame (16.7 ms at 30 fps). 🟡 That is below what viewers notice (editors
commonly cut a frame early so the image change leads the sound). The verifier's `BEAT_SYNC`
check proves two things: every planned cut is within half a frame of its beat, and the music in
the render sits where the plan put it, found by onset cross-correlation.

**Limits.** A talking-head cut can only move inside its pause, so a fast talker gets fewer
cuts on the beat; the notes say how many made it. Rubato, live and ambient tracks with no steady
pulse return confidence below 0.3: there, cut to phrases, not beats.

## 6. Packs: where the sounds, music and grades come from

| Source | What | Licence |
|---|---|---|
| Built-in (code) | 5 grades (teal-orange, moody, warm-vlog, punch, bleach), grain/vignette/letterbox, 8 synthesized sounds | no third-party rights |
| OpenFilm library (`npm i -g openfilm`) | ~1,222 music tracks (tempo, energy), ~5,436 sound effects, 66 grades | 🟢 CC0 1.0: any use, commercial too, no credit |
| Your own | Artlist, Epidemic, etc. | yours to hold, per platform and per client |

`asset_packs.py pack --style motivation --dir packs/motivation` builds a grade, a music track and
three sounds (hit, whoosh, riser) in ~7 s. Pass `pack.json` to either planner with `--pack`.
OpenFilm grades are baked into a 33³ `.cube` LUT, applying its matrix, then saturation, then
curves, in the order its own renderer uses. 🔴 "Free sound effect packs on YouTube are free to use."
Many are re-uploads of paid libraries; use sources that state a licence.

## Sources

1. Murch, W. *In the Blink of an Eye* (2nd ed.), Silman-James, 2001: the rule of six.
2. Ellis, D. P. W. "Beat Tracking by Dynamic Programming", *Journal of New Music Research* 36(1),
   2007: tempo prior and DP tracker.
3. Bello, J. P. et al. "A Tutorial on Onset Detection in Music Signals", *IEEE Trans. Speech and
   Audio Processing* 13(5), 2005: band-wise energy-rise onset functions.
4. Böck, S., Krebs, F., Widmer, G. "Joint Beat and Downbeat Tracking with Recurrent Neural
   Networks", ISMIR 2016: downbeats as a separate, harder problem (why 4/4 is stated as assumed).
5. OpenFilm, `library/LICENSE.md` (github.com/openfilm/openfilm): CC0 1.0 dedication of the
   library's sounds, music, grades, transitions and effects.
6. Creative Commons, "CC0 1.0 Universal Public Domain Dedication" legal code.
7. YouTube Help, "Copyright strikes basics" and "Content ID": unlicensed music and speeches get a
   video muted, blocked or struck.
