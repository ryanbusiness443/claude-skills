# youtube-editor

A YouTube video editing agent built for precision. It decides **what** to cut the way an editor
would, and hands **where** to five stdlib tools on ffmpeg that cut to the exact frame and audio
sample. Then it checks the render. Nothing is reported as done until the verifier passes.

```text
raw.mp4 ──probe/analyze──▶ proposed cuts ──you approve──▶ edl.json
        ──edit_planner──▶ plan.json (frame + sample exact, findings)
        ──render_engine──▶ final.mp4 ──edit_verifier──▶ PASS / FAIL (max 3 rounds)
        ──timeline_remapper──▶ chapters block + final.srt
```

## Install

```bash
/plugin marketplace add alirezarezvani/claude-skills
/plugin install youtube-editor@claude-code-skills
```

Requires **ffmpeg ≥ 5.1** (`brew install ffmpeg`, `sudo apt install ffmpeg`, `winget install ffmpeg`).
Optional: word timestamps from `faster-whisper` / WhisperX or an existing transcript JSON. These
enable word-safe cuts and filler removal.

## Use

```text
/cs-youtube-edit raw.mp4 words.json chapters.txt
/cs-youtube-verify plan.json final.mp4
```

Or run the tools directly. Each one supports `--help`, `--sample` (a self-contained demo on a
generated clip) and `--output json`:

```bash
S=skills/youtube-editor/scripts
python3 $S/media_analyzer.py propose raw.mp4 --words words.json --edl-out edl.json
python3 $S/edit_planner.py edl.json --snap-words --plan-out plan.json
python3 $S/render_engine.py plan.json -o final.mp4
python3 $S/edit_verifier.py plan.json final.mp4
python3 $S/timeline_remapper.py chapters plan.json chapters.txt
python3 $S/timeline_remapper.py captions plan.json --words words.json -o final.srt
```

## What "top precision" means here, in checks

| Check | Measured result on the test suite |
|---|---|
| Output frame count = plan | exact (4080/4080 frames, 61-piece 1080p edit) |
| Frame after every cut = intended source frame | 100/100 boundaries at offset 0 |
| Audio alignment inside each piece (cross-correlation) | 0.0 ms worst lag; a 10 ms shift is caught |
| Beeps at known times through 3 cuts + 44.1→48 kHz resample | ≤ 1 sample error |
| Source where audio starts 278 ms after video | 0.06 ms worst error |
| A/V end sync | ≤ 0.13 ms |
| Loudness | −14 LUFS ±1, true peak ≤ −1 dBTP (+0.5 tolerance after AAC) |

The verifier ships two negative controls in `edit_verifier.py --sample` — the same render checked
against a plan shifted by one frame, and a render with audio 10 ms late. Both must FAIL, and do.

## Design decisions

- **No stream copy for cuts.** `-c copy` starts a piece on a keyframe, which can be seconds early.
  Every piece is re-encoded, selected by frame index and sample index in one decode pass.
- **Exact arithmetic.** Times are `fractions.Fraction`, never floats. 29.97 fps is 30000/1001. SMPTE
  drop-frame timecode is supported.
- **Audio follows video.** Each piece's sample count comes from the output frame timeline, so
  rounding never accumulates however many cuts there are. Leading silence is inserted when a
  source's audio starts after its video.
- **Short fades, not crossfades.** A 12 ms fade at each cut removes clicks without changing length.
  A crossfade would shorten the audio and break the frame lock.
- **Honest uncertainty.** Static shots and held tones are reported `AMBIGUOUS`, not passed.
- **Bugs the verifier caught during the build** are now regression cases: a duplicated frame after
  seeking in raw output, audio landing 278 ms early when a source's audio starts late, and
  dynamic-mode loudnorm adding 27 ms and overshooting true peak.

## Scope

Edits local files only. It does not download or upload videos, does not need API keys, and never
modifies the source file. For transcripts, search and channel data on *published* videos, use
`marketing-skill/skills/youtube-full`.

## License

MIT, part of [claude-skills](https://github.com/alirezarezvani/claude-skills).
