# YouTube delivery spec

What the renderer writes and the verifier checks, with where each number comes from.
🟢 YouTube Help Center / standard · 🟡 measured or widely reproduced practice · 🔴 folklore.

## 1. Recommended upload encoding (YouTube Help, answer 1722171) 🟢

| Setting | YouTube recommendation | Renderer |
|---|---|---|
| Container | MP4, moov atom at the front (fast start) | `-movflags +faststart`; verifier reads box order |
| Video codec | H.264, High profile, progressive | `libx264 -profile:v high`, `bwdif` if interlaced |
| GOP | Closed GOP, half the frame rate | `-g round(fps/2)`, `open-gop=0`, `scenecut=0` |
| B-frames | 2 consecutive | `-bf 2` |
| Chroma | 4:2:0 | `-pix_fmt yuv420p` |
| Frame rate | Same as recorded | plan fps, CFR; never converted |
| Audio | AAC-LC, 48 or 96 kHz; stereo 384 kbps, mono 128 kbps | AAC 48 kHz, 384k stereo / 192k mono |
| Colour (SDR) | BT.709 | tags BT.709 when an HD source is untagged |

Recommended SDR bitrates (Mbps, standard / high frame rate): 2160p 35–45 / 53–68 · 1440p 16 / 24 ·
1080p 8 / 12 · 720p 5 / 7.5. The renderer uses CRF 18 instead of a fixed bitrate, which lands above
these floors for typical talking-head and screen content; YouTube re-encodes everything, so upload
quality is the ceiling of what viewers see. `draft` (CRF 28, veryfast) is for previews only.

- 🟡 The same page asks for "no edit lists". ffmpeg writes a one-entry edit list to hide AAC encoder
  priming (1024 samples); this is what keeps audio sample-aligned and is accepted by YouTube in
  practice. If an upload ever fails processing, re-mux with `-use_editlist 0` and accept a ~21 ms
  audio delay (inside the lip-sync window in `precision_editing_canon.md` §4).
- 🟡 Uploading 1080p content upscaled to 1440p/4K gets a higher-bitrate encode tier from YouTube. This
  is a creator practice, not a documented policy; only the `youtube-1440p` / `youtube-4k` presets do it,
  and only when the user picks them.

## 2. Loudness

- 🟢 Measurement: ITU-R BS.1770 (K-weighted LUFS, true-peak via oversampling); EBU R 128 / Tech 3342 for
  loudness range (LRA).
- 🟡 YouTube normalizes playback to roughly −14 LUFS integrated and only turns loud content *down*; quiet
  content is not raised. This is measured from "Stats for nerds → content loudness", not published.
  Mastering at −14 LUFS means nothing is turned down and nothing is left quiet.
- 🟢 True-peak ceiling −1 dBTP leaves headroom for the lossy re-encode, which can create inter-sample
  overs. The renderer measures in pass 1 and applies `loudnorm` in linear mode in pass 2, so dynamics
  are preserved whenever the target is reachable; the verifier re-measures the actual file.
- Speech with music beds: if LRA is over ~11 LU, the linear pass may be impossible and `loudnorm`
  falls back to dynamic mode. The verifier still checks the result; it does not trust the filter.

## 3. Chapters (YouTube Help, answer 9884579) 🟢

- First timestamp must be `0:00`; at least three timestamps, ascending; each chapter at least 10 s.
  If any rule fails YouTube ignores *all* of them, so `timeline_remapper.py chapters` enforces the rules
  and reports every change (`MOVED`, `COLLAPSED`, `TOO_SHORT`, `FIRST_NOT_ZERO`, `TOO_FEW`).

## 4. Shorts 🟢

- Square or vertical; uploads up to 3 minutes count as Shorts. `youtube-shorts` centre-crops to 9:16,
  scales to 1080×1920, and the planner blocks an edit longer than 180 s (`TOO_LONG`). Re-plan the same
  EDL with `--preset youtube-shorts`; do not re-cut by hand.

## 5. Captions 🟢

- YouTube accepts SubRip (`.srt`) and WebVTT. `timeline_remapper.py captions` writes SRT, clips cues
  that cross a cut, drops cues fully inside one, and removes overlaps. With `--words` it rebuilds cues
  from kept words only, so a removed "um" also leaves the caption text. Lines are wrapped at 42
  characters, two lines per cue — the common broadcast reading limit.

## Sources

1. YouTube Help, "Recommended upload encoding settings" (answer 1722171).
   https://support.google.com/youtube/answer/1722171
2. YouTube Help, "Video chapters" (answer 9884579). https://support.google.com/youtube/answer/9884579
3. YouTube Help, "Upload YouTube Shorts" (answer 12779649). https://support.google.com/youtube/answer/12779649
4. YouTube Help, "Supported subtitle and closed caption files" (answer 2734698).
   https://support.google.com/youtube/answer/2734698
5. ITU-R BS.1770, *Algorithms to measure audio programme loudness and true-peak audio level*.
6. EBU R 128 and EBU Tech 3342 (loudness normalisation; loudness range).
7. FFmpeg `loudnorm` filter documentation (two-pass, `linear=true`). https://ffmpeg.org/ffmpeg-filters.html#loudnorm
