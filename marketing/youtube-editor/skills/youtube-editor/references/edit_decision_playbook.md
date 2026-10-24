# Edit decision playbook

The judgement layer: what the agent cuts, what it refuses to cut, and how it recovers when the
verifier fails. 🟢 research or documentation · 🟡 editing practice · 🔴 folklore.

## 1. Pacing defaults

| Content | Padding each side of a cut | Min silence to cut | Why |
|---|---|---|---|
| Talking head, energetic | 0.10–0.15 s | 0.5 s | 🟡 "jump-cut" vernacular; tight reads as confident |
| Tutorial / teaching | 0.20–0.30 s | 0.8 s | 🟡 viewers need a beat to absorb a step |
| Interview / emotional | 0.30 s+, review by ear | 1.2 s | 🟢 Murch: emotion outranks rhythm; pauses carry meaning |
| Screen recording | 0.15 s | 0.6 s | 🟡 cursor motion often continues through silence — watch it |

- Raise `--noise-db` toward −30 in noisy rooms; lower toward −40 for a clean studio. Check the first
  three proposed cuts by ear before trusting the rest.
- A cut removing fewer than 3 frames is a visible jump with no time saved (`MICRO_CUT`): delete it.
- A kept piece under ~6 frames reads as a flash frame (`MICRO_KEEP`): extend it or remove it.

## 2. Filler words

- 🟢 "Uh" and "um" are words speakers use to signal a delay, not random noise (Clark & Fox Tree, 2002).
  Removing them usually tightens delivery, but a filler before a hard answer can be the honest beat of
  the video. Proposals cover only unambiguous disfluencies (`um`, `uh`, `erm`, `hmm`, …); "like",
  "so" and "you know" are never auto-proposed because they carry meaning too often.
- The filler cut takes the pause after the word too, leaving a 60 ms beat so speech does not collide.
- Repeated starts and retakes ("let me say that again") are content decisions: the agent finds them
  in the transcript and *proposes* keeping the last clean take, with both takes' times shown.

## 3. Approval gates

1. Proposed cut list → user approves or edits before planning.
2. Planner warnings → each one fixed or explicitly accepted by name.
3. Draft preview → user watches before the full-quality render on long videos.
4. Verifier PASS report → shown with the delivery, including any `AMBIGUOUS` boundaries.

## 4. When the verifier fails

| Failed check | Usual cause | Fix |
|---|---|---|
| `FRAME_COUNT` off by N | VFR source not conformed; plan made from a different file | re-probe, re-plan from the exact source; confirm `vfr` in the plan |
| `CUT_FRAMES` offset ±1 everywhere | source has a non-zero video start time or edit list | re-plan (the planner reads start times); re-render |
| `CUT_FRAMES` wrong at one cut | source file changed after planning | re-plan; never reuse a plan across files |
| `CUT_FRAMES` all AMBIGUOUS | static shot (slides, locked-off camera) | not an error; confirm by ear/eye at those times |
| `AV_SYNC` > 1 frame | audio stream shorter than video (recorder dropped audio) | trim the EDL end to the audio end, re-plan |
| `LOUDNESS` off target | `loudnorm` fell back to dynamic mode on wide-LRA audio | accept ±1 LU drift, or compress dialog first; never skip the check |
| `UPLOAD_SPEC` | output path not `.mp4`, or a preset edited by hand | render with a stock preset to `.mp4` |

Loop budget: at most **3** render→verify rounds. The fourth failure goes to the user with every
verifier report, the plan, and what was tried — never a silent retry.

## 5. EDL authoring notes

- `"mode": "cut"` lists what to remove (what `propose` emits); `"mode": "keep"` lists what to keep.
- To rearrange content deliberately, use keep mode with `"allow_reorder": true`; otherwise ranges are
  sorted and `REORDERED` is reported.
- Times accept seconds, `MM:SS.mmm`, `HH:MM:SS.mmm`, SMPTE `HH:MM:SS:FF` (`;FF` drop-frame) and `123f`.
- Plans embed the source path and frame counts: one plan, one source file.

## Sources

1. Clark, H. H., & Fox Tree, J. E. (2002). "Using uh and um in spontaneous speaking." *Cognition*, 84(1), 73–111.
2. Murch, W. *In the Blink of an Eye* (2nd ed.). Silman-James, 2001.
3. Dmytryk, E. *On Film Editing*. Focal Press, 1984 — cut on motion; never cut without a reason.
4. Radford, A. et al. (2022). "Robust Speech Recognition via Large-Scale Weak Supervision" (Whisper), and
   Bain, M. et al. (2023). "WhisperX: Time-Accurate Speech Transcription of Long-Form Audio" — word
   timestamps carry tens of milliseconds of error, which is why proposals keep padding.
5. FFmpeg `silencedetect` documentation. https://ffmpeg.org/ffmpeg-filters.html#silencedetect
6. YouTube Help, "Video chapters" (answer 9884579).
7. YouTube Creator Academy material on retention and pacing (🟡 practice guidance, not data).
