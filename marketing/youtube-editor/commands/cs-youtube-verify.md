---
name: "cs-youtube-verify"
description: "/cs-youtube-verify — Prove a render matches its edit plan: exact frame count, per-cut frame matching against the source, audio cross-correlation, A/V sync, −14 LUFS loudness, and YouTube upload spec. PASS/FAIL with the cause of every failure."
argument-hint: "[plan.json] [rendered.mp4]"
---

# /cs-youtube-verify — Check a render, not a promise

**Command:** `/cs-youtube-verify plan.json final.mp4`

## When to run

- After any render, before calling an edit done.
- When a render from another tool is suspected of drifting or clipping words.

## When NOT to run

- No plan yet → [`/cs-youtube-edit`](cs-youtube-edit.md) builds one.

## Steps

1. `python3 ../skills/youtube-editor/scripts/edit_verifier.py plan.json final.mp4 --report-out verify.json`
2. On FAIL, map each failed check to its cause with
   [`edit_decision_playbook.md` §4](../skills/youtube-editor/references/edit_decision_playbook.md).
3. Report `AMBIGUOUS` boundaries (static shots, held tones) by timestamp so a human can spot-check.

## What you get

A PASS/FAIL table — `FRAME_COUNT`, `FRAME_RATE`, `DURATION`, `AV_SYNC`, `AUDIO_ALIGN`,
`CUT_FRAMES`, `LOUDNESS`, `UPLOAD_SPEC` — and, for every failure, the likely cause and fix.
