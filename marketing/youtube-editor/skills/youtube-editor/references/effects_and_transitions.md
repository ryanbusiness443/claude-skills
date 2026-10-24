# Effects and transitions

How transitions and effects are planned, rendered and proven, and when to use them.
🟢 documentation or standard · 🟡 editing practice · 🔴 folklore (named as such).

## 1. Transitions change the timeline, so they are planned, not bolted on

- A transition of D frames overlaps the end of piece A with the start of piece B. Piece B
  therefore starts at `P_B = P_A + n_A − D`, and the edit is exactly D frames shorter per
  transition. `edit_planner.py` computes every `out_start_frame` this way, so the frame count,
  chapters, captions and effect windows already account for the overlap.
- A piece must keep at least one clean frame between its incoming and outgoing transitions
  (`TRANSITION_TOO_LONG` blocks otherwise). A transition longer than a neighbouring piece is
  shortened and reported as `TRANSITION_SHORTENED`.
- 🟢 Video uses ffmpeg's `xfade` (50+ styles). Each piece is its own input, seeked to half a frame
  before its first frame, so ffmpeg's accurate seek emits exactly that frame. Inputs decode only
  when the chain reaches them instead of buffering later pieces' frames (measured: 21 pieces,
  20 transitions, 1080p, 1.6 GB peak memory). Plan very long transition-heavy edits in sections.
- The verifier proves a transition by rebuilding its middle frame from the two source pieces with
  the same `xfade` (plus any colour, effect or captions on that frame) and requiring the output
  to match it more closely than either piece. On the stress edit, 19 of 20 matched within 0.23;
  the 20th matched (0.2) but its two pieces were too alike to separate, so it reports AMBIGUOUS.
- 🟢 `concat` outputs a microsecond timebase. The renderer resets it to 1/fps after every hard-cut
  join, because a following `xfade` rejects mismatched timebases. The mixed cut + crossfade
  case in the verifier's `--sample` exists to catch exactly that.
- Audio crossfades are built sample-exactly: A fades out over its last `ov` samples, B fades in
  and is delayed by `len(A) − ov` samples, and the two are summed. ffmpeg's `acrossfade` is not
  used. In the build it rounded the overlap to its internal frame size, producing 256 extra
  samples (~5 ms of drift), which `AUDIO_ALIGN` caught.

## 2. Effects

| Effect | Timing | How it renders | How it is verified |
|---|---|---|---|
| `zoom` | source range | split, crop + scale, overlay gated by `between(n,A,B-1)` | frame A and B−1 match the source *with* zoom; A−1 and B match it *without* |
| `text` | source range | `drawtext` from a text file (no escaping bugs), gated by frame number | same on/off edge test |
| `blur` | source range | crop region, `boxblur`, overlay back | same on/off edge test |
| `color` / `lut` | whole video | `eq` / `lut3d` | applied to every source thumbnail before comparison |
| `captions` | whole video | `subtitles` (libass) from cues remapped through the edit | source frames re-captioned at the matching output time: the output must match *with* captions and differ *without* |
| `music` | whole video | looped, trimmed to the exact sample count, ducked by a voice-keyed `sidechaincompress`, mixed before loudness | loudness and true peak on the final mix |
| `fade_in` / `fade_out` | edges | `fade` by frame count, `afade` by duration | first/last frame mean luma ≤ 24 |

- Gating by frame number (`n`) rather than time removes the rounding window at effect edges:
  the effect starts and stops on the exact planned frame, and the `EFFECTS` check proves it with
  frames on both sides of each edge. The verifier's `--sample` moves a zoom window 2 frames and
  confirms that FAILS.
- Local effects are written in source time because the content is what they belong to. Re-cutting
  the video moves the zoom with the sentence it emphasises. Use `"time": "output"` for a fixed
  position in the final timeline (for example, an end-screen caption).
- An effect over a transition still renders, but its edge frames cannot be compared with a single
  source frame, so it is reported `SKIP`. The planner warns `EFFECT_OVER_TRANSITION` in advance.

## 3. Loudness with effects

- Music and fades change the programme, so loudness is measured on the *final mix* in pass 1.
- The audio is encoded first, to its own AAC file, and its true peak is re-measured. If the encode
  pushed it over the ceiling, the limiter (running at 4× oversampling) is tightened by exactly the
  measured overshoot and only the audio is re-encoded, up to twice. The video is then encoded once
  and the audio copied in.
- 🟢 Low-bitrate AAC re-creates noise with peaks that no limiter controls. The `draft` preset was
  raised from 128 to 192 kbps after a 64 kbps mono preview failed its own true-peak check.

## 4. Taste: when to use what

- 🟡 **Hard cuts are the default for talking-head YouTube.** Viewers read a crossfade between two
  takes of the same shot as hesitation. Use a crossfade for a change of time or place, and a dip to
  black for a section break.
- 🟡 **Zoom punch-ins (1.1–1.3×) hide jump cuts** in single-camera talking-head footage. Alternate
  zoomed and wide on consecutive pieces rather than zooming every piece.
- 🟡 **Burned captions earn their place on Shorts**, which are mostly watched muted. On long-form
  videos, upload the `.srt` instead: viewers can switch it off and it is indexed.
- 🟡 Music beds sit −18 to −24 dB under speech, ducked. If you can hear the music over the words,
  it is too loud.
- 🔴 "Every cut needs a transition" is folklore. Murch's hierarchy puts emotion and story above
  rhythm and everything technical; a transition that draws attention to itself breaks that.

## Sources

1. FFmpeg Filters Documentation — `xfade`, `drawtext`, `subtitles`, `boxblur`, `overlay`, `eq`,
   `lut3d`, `sidechaincompress`, `amix`, `afade`, `adelay`, `fade`. https://ffmpeg.org/ffmpeg-filters.html
2. FFmpeg Wiki, "Seeking" (accurate input seeking). https://trac.ffmpeg.org/wiki/Seeking
3. libass / Advanced SubStation Alpha style reference (force_style fields, PlayResY 288 default).
4. Murch, W. *In the Blink of an Eye* (2nd ed.). Silman-James, 2001 — the rule of six.
5. Dancyger, K. *The Technique of Film and Video Editing* (6th ed.). Routledge, 2018 — dissolves
   for time/place transitions, cuts for continuity.
6. YouTube Help, "Upload YouTube Shorts" (answer 12779649) — vertical, muted-first viewing context.
7. ITU-R BS.1770 — true-peak measurement by oversampling.
