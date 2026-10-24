# Precision editing canon

How the tools get cuts exactly right, and the traps they are built to avoid. Confidence per claim:
🟢 primary documentation or standard · 🟡 widely reproduced practice · 🔴 folklore (named as such).

## 1. Why stream copy cannot cut precisely

- 🟢 A compressed H.264 stream can only be decoded starting from a keyframe (IDR). `ffmpeg -ss X -c copy`
  therefore starts the piece at a keyframe at or before X. Camera and screen-recorder GOPs of 2–10 s are
  common, so a "lossless" cut can be seconds off, or carry frozen/garbled frames until the next keyframe.
- 🟢 Since FFmpeg 2.1, input seeking (`-ss` before `-i`) is frame-accurate *when transcoding*: ffmpeg
  decodes from the previous keyframe and discards frames before the target. (FFmpeg wiki, "Seeking".)
- The renderer goes further than seeking: it selects frames by **index** (`select=between(n,S,E-1)`),
  which has no timestamp rounding at all, in a single decode pass. `media_analyzer.py probe` reports
  the source's largest keyframe gap so the user can see what stream copy would have cost.

## 2. Time is a rational number

- 🟢 NTSC-family rates are exact fractions: 23.976 = 24000/1001, 29.97 = 30000/1001, 59.94 = 60000/1001.
  Treating 29.97 as a float accumulates a full frame of error within roughly 9 minutes of arithmetic at
  millisecond rounding. Every tool keeps `Fraction` values end to end and stores them as `"num/den"`.
- 🟢 Frame `n` of a constant-frame-rate stream starts at `n / fps` after the first frame. Cut points are
  snapped to the nearest boundary (worst case half a frame, reported as `SNAPPED`), or outward when a
  word must be preserved.
- 🟢 SMPTE ST 12-1 timecode labels frames. Drop-frame (`HH:MM:SS;FF`) skips labels 00 and 01 every minute
  except each tenth minute (four labels at 59.94) so the label tracks wall-clock time. `parse_time`
  implements this; non-drop `HH:MM:SS:FF` at 29.97 drifts 3.6 s per hour from wall-clock, by design.
- 🟢 A container's duration field is rounded (often to microseconds), so `duration × fps` can land a
  hair under the true frame count. The planner counts packets (`ffprobe -count_packets`) instead.

## 3. Variable frame rate and interlacing

- 🟡 Phones and many screen recorders write variable-frame-rate files; `r_frame_rate` and
  `avg_frame_rate` then disagree. Frame index no longer maps linearly to time, so the renderer conforms
  to CFR (`fps` filter) before selecting, and the planner warns `VFR`.
- 🟢 YouTube asks for progressive scan. Interlaced sources (`field_order` tt/bb) are deinterlaced with
  `bwdif` in `send_frame` mode, which keeps one output frame per input frame so indices stay valid.

## 4. Audio: sample-exact and click-free

- Audio boundaries are derived from the **output** frame timeline: piece *i* gets
  `round(out_end·sr) − round(out_start·sr)` samples, starting at the sample nearest its source time
  (corrected for any audio/video start offset). Rounding error is bounded by half a sample and never
  accumulates, however many cuts there are. Tested: beeps at known times land within one sample after
  three cuts and a 44.1 → 48 kHz resample.
- 🟢 Cutting a waveform mid-cycle creates a step discontinuity, heard as a click. Each internal cut gets
  a short fade out/in (default 12 ms). Fades keep the length exact. A transition is different: it is a
  planned overlap, and the timeline shrinks by exactly its frames (see `effects_and_transitions.md`).
- 🟢 Lip-sync detectability (ITU-R BT.1359): roughly 45 ms audio-early or 125 ms audio-late. The verifier
  holds output A/V to one frame (33 ms at 30 fps), well inside that window.

## 5. Proving it: boundary frame matching

- The verifier decodes the output frame on each side of every cut and compares it, as a 64×36 grey
  thumbnail, with source frames −2…+2 around where the plan says it came from. The best match must be
  offset 0 and visually close (mean absolute difference ≤ 12/255).
- 🟢 Static shots make neighbouring frames indistinguishable; when the best and runner-up are within
  0.75, the boundary is reported `AMBIGUOUS` rather than passed. Honest uncertainty beats a false PASS.
- Every `--sample` run includes a negative control: the same render checked against a plan shifted by
  one frame must FAIL. A verifier that cannot fail proves nothing.
- One debugging lesson is encoded in `grab_frames`: with raw output, ffmpeg's default CFR vsync
  duplicates the first frame after a seek. `-fps_mode passthrough` is required (FFmpeg ≥ 5.1).

## Sources

1. FFmpeg Filters Documentation — `select`, `trim`/`atrim`, `afade`, `loudnorm`, `silencedetect`,
   `ebur128`, `bwdif`, `fps`. https://ffmpeg.org/ffmpeg-filters.html
2. FFmpeg Wiki, "Seeking". https://trac.ffmpeg.org/wiki/Seeking
3. SMPTE ST 12-1, *Time and Control Code* (drop-frame timecode definition).
4. ITU-R BT.1359-1, *Relative timing of sound and vision for broadcasting*.
5. ITU-T H.264 / ISO/IEC 14496-10 — IDR pictures and GOP structure.
6. Apple Technical Note TN2310 / QuickTime file format — edit lists and media time.
7. Murch, W. *In the Blink of an Eye* (2nd ed., Silman-James, 2001) — the cut serves emotion and
   story first; precision is what lets a cut go unnoticed.
