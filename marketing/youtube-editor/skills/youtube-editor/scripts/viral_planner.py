#!/usr/bin/env python3
"""viral_planner.py — turn a talking-head transcript into a retention edit (EDL).

What a short-form editor does by hand, as deterministic rules over word
timestamps. Every decision is written to the notes with its reason, and the
result is an ordinary EDL that goes through edit_planner.py, render_engine.py
and edit_verifier.py like any other edit.

  1. Hook       first words land on frame 1: lead-in silence cut; a hook title
                card from the first sentence (or --hook); flash + impact on
                frame 1 (punchy/insane).
  2. Pace       jump cuts on every pause above the intensity's gap threshold.
  3. Rhythm     the frame never sits still longer than the intensity allows:
                sentences alternate wide/tight framing, long ones are split.
  4. Emphasis   numbers and power words get a punch-in plus a pop.
  5. Shock      (insane) negative words get a black-and-white hit + camera
                click; the hook gets a shake + bass drop.
  6. CTA        the call-to-action sentence gets the tightest framing + a ding.
  7. Finish     karaoke captions, colour pop, progress bar (shorts), music bed
                ducked under the voice, and a hard loop ending on shorts.

Intensity: clean (talks, tutorials) · punchy (default; most reels) · insane
(hype, entertainment). Restraint is a feature: "insane" on a serious topic
reads as noise, and the notes say so.

Exit codes: 0 ok · 4 usage/input · 6 ffmpeg missing.

Examples:
  python3 viral_planner.py raw.mp4 --words words.json --edl-out reel.edl.json
  python3 viral_planner.py raw.mp4 --words words.json --intensity insane --music bed.mp3 \\
      --hook "STOP DOING THIS" --edl-out reel.edl.json --notes-out notes.md
  python3 viral_planner.py raw.mp4 --words words.json --format long --edl-out yt.edl.json
  python3 viral_planner.py --sample
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ytedit_core as core  # noqa: E402

INTENSITY = {
    #           gap to cut, pad kept, max still s, punch gap s, whoosh gap s
    "clean": {"gap": "0.40", "pad": "0.10", "still": "4.0", "punch": "6.0", "whoosh": "99",
              "zoom": [1.0, 1.10], "punch_scale": 1.12},
    "punchy": {"gap": "0.22", "pad": "0.06", "still": "2.5", "punch": "3.0", "whoosh": "2.5",
               "zoom": [1.0, 1.14, 1.0, 1.22], "punch_scale": 1.18},
    "insane": {"gap": "0.14", "pad": "0.04", "still": "1.6", "punch": "1.5", "whoosh": "1.2",
               "zoom": [1.0, 1.18, 1.08, 1.28], "punch_scale": 1.22},
}
POWER_WORDS = {
    "you", "your", "now", "free", "secret", "never", "always", "best", "worst", "first",
    "only", "stop", "why", "how", "mistake", "money", "fast", "easy", "instantly", "today",
    "everyone", "nobody", "every", "biggest", "real", "truth", "insane", "crazy", "hack",
    "proven", "guaranteed", "simple", "exactly", "million", "thousand", "hundred", "double",
}
NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "twenty", "fifty", "hundred", "thousand", "million", "billion"}
NEGATIVE_WORDS = {"never", "stop", "mistake", "wrong", "worst", "fail", "failed", "problem",
                  "broke", "lose", "lost", "nobody", "don't", "can't", "won't", "dead"}
CTA_WORDS = {"follow", "subscribe", "link", "tap", "click", "comment", "share", "save", "buy",
             "sign", "dm", "download", "join", "book", "grab", "get", "visit"}


def _tok(word):
    return re.sub(r"[^a-z0-9'$%]", "", word.lower())


def _sentences(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if w["word"].rstrip("\"')").endswith((".", "?", "!")):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _ts(t):
    return core.fmt_ts(t, 3)


def plan_viral(source, words, intensity="punchy", fmt="short", music=None, hook=None,
               emphasis=(), focus=(0.5, 0.40), duration=None):
    cfg = INTENSITY[intensity]
    gap, pad = Fraction(cfg["gap"]), Fraction(cfg["pad"])
    max_still = Fraction(cfg["still"])
    notes, effects, cuts = [], [], []
    if not words:
        raise core.ToolError("no words: the viral planner needs word timestamps")
    if duration is None:
        duration = core.to_fraction(core.probe(source)["duration"])

    # 1-2. Cuts: lead-in, trailing, and every pause above the gap threshold.
    first, last = words[0], words[-1]
    lead_end = max(Fraction(0), first["start"] - Fraction(2, 100))
    if lead_end > Fraction(5, 100):
        cuts.append({"start": "0", "end": _ts(lead_end), "label": "lead-in: first word on frame 1"})
    for a, b in zip(words, words[1:]):
        g = b["start"] - a["end"]
        if g > gap:
            lo, hi = a["end"] + pad, b["start"] - pad
            if hi - lo >= Fraction(8, 100):
                cuts.append({"start": _ts(lo), "end": _ts(hi),
                             "label": "jump cut: %.2fs pause after %r" % (float(g), a["word"])})
    tail = last["end"] + (Fraction(5, 100) if fmt == "short" else Fraction(25, 100))
    if duration - tail > Fraction(5, 100):
        cuts.append({"start": _ts(tail), "end": _ts(duration),
                     "label": "trailing silence (short: hard end so it loops)"
                     if fmt == "short" else "trailing silence"})
    removed = sum((core.parse_time(c["end"]) - core.parse_time(c["start"]) for c in cuts),
                  Fraction(0))
    notes.append("Pace: %d cuts remove %.1fs of %.1fs (pauses over %ss cut, %ss kept each side)."
                 % (len(cuts), float(removed), float(duration), cfg["gap"], cfg["pad"]))

    # 3. Rhythm: alternate framing per sentence, split long sentences so the
    # frame never holds still longer than max_still.
    sentences = _sentences(words)
    levels = cfg["zoom"]
    k = 0
    blocks = []
    for sent in sentences:
        cur = [sent[0]]
        for w in sent[1:]:
            if w["end"] - cur[0]["start"] > max_still and w["start"] - cur[-1]["end"] < gap:
                blocks.append(cur)
                cur = [w]
            else:
                cur.append(w)
        blocks.append(cur)
    for blk in blocks:
        scale = levels[k % len(levels)]
        k += 1
        if scale > 1.0:
            effects.append({"type": "zoom", "start": _ts(blk[0]["start"] - pad),
                            "end": _ts(blk[-1]["end"] + pad), "scale": scale,
                            "center": list(focus)})
    notes.append("Rhythm: %d framing blocks alternating %s, none longer than %ss."
                 % (len(blocks), "/".join("wide" if z == 1.0 else "%.2fx" % z for z in levels),
                    cfg["still"]))

    # 1. Hook.
    hook_text = (hook or " ".join(w["word"] for w in sentences[0])).strip().upper()
    hook_words = hook_text.split()
    if len(" ".join(hook_words)) > 48:
        hook_words = hook_words[:8]
        hook_text = " ".join(hook_words) + "…"
    # Balanced lines short enough for the frame: ~16 characters on a vertical
    # reel, ~28 on landscape.
    width = 16 if fmt == "short" else 28
    while True:
        lines, line = [], ""
        for w in hook_words:
            if line and len(line) + 1 + len(w) > width:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        lines.append(line)
        if len(lines) <= 3:
            break
        width += 2  # never drop words: widen, and the renderer shrinks to fit
    hook_text = "\n".join(lines)
    hook_end = min(sentences[0][-1]["end"], first["start"] + Fraction(5, 2))
    effects.append({"type": "text", "start": _ts(first["start"]), "end": _ts(hook_end),
                    "text": hook_text, "position": "top", "style": "hook",
                    "size": 0.042 if fmt == "short" else 0.06})
    notes.append("Hook: title card %r for the first %.1fs." % (hook_text.replace("\n", " / "),
                                                              float(hook_end - first["start"])))
    if intensity != "clean":
        effects.append({"type": "flash", "start": _ts(first["start"]),
                        "end": _ts(first["start"] + Fraction(1, 5)), "peak": 0.7})
        effects.append({"type": "sfx", "sound": "boom", "at": _ts(first["start"])})
        notes.append("Hook: white flash + boom on frame 1 (pattern break before the brain "
                     "decides to swipe).")
    if intensity == "insane":
        effects.append({"type": "shake", "start": _ts(first["start"]),
                        "end": _ts(first["start"] + Fraction(2, 5)), "intensity": 0.012})
        effects.append({"type": "sfx", "sound": "bass_drop", "at": _ts(first["start"])})

    # 4-5. Emphasis punches and shock hits.
    punch_gap, last_punch = Fraction(cfg["punch"]), Fraction(-99)
    emph = {_tok(e) for e in emphasis}
    shocks = 0
    for w in words[1:]:
        t = _tok(w["word"])
        is_num = bool(re.search(r"\d", t)) or t in NUMBER_WORDS or "$" in w["word"] or "%" in t
        if not (is_num or t in POWER_WORDS or t in emph):
            continue
        if w["start"] - last_punch < punch_gap or w["start"] < hook_end:
            continue
        last_punch = w["start"]
        effects.append({"type": "zoom", "start": _ts(w["start"] - Fraction(3, 100)),
                        "end": _ts(w["end"] + Fraction(12, 100)), "scale": cfg["punch_scale"],
                        "center": list(focus)})
        effects.append({"type": "sfx", "sound": "pop", "at": _ts(w["start"])})
        notes.append("Emphasis: punch-in + pop on %r at %s." % (w["word"], _ts(w["start"])))
        if intensity == "insane" and t in NEGATIVE_WORDS and shocks < 3:
            shocks += 1
            effects.append({"type": "bw", "start": _ts(w["start"]),
                            "end": _ts(w["end"] + Fraction(1, 10))})
            effects.append({"type": "sfx", "sound": "camera", "at": _ts(w["start"])})
            notes.append("Shock: black-and-white hit on %r." % w["word"])

    # Whooshes on the jump cuts, spaced so they do not become wallpaper.
    whoosh_gap, last_w = Fraction(cfg["whoosh"]), Fraction(-99)
    for c in cuts[1:]:
        t = core.parse_time(c["end"])
        if t - last_w >= whoosh_gap and t < last["end"]:
            last_w = t
            effects.append({"type": "sfx", "sound": "whoosh", "at": _ts(t)})
    if whoosh_gap < 99:
        notes.append("Sound: whoosh on jump cuts at most every %ss." % cfg["whoosh"])

    # 6. CTA.
    # A call to action is an imperative: a CTA verb opening the sentence ("Tap
    # build my plan", "Follow for more"). A mid-sentence "buy" in "people want
    # to buy" is not one. Prefer the latest such sentence.
    def opener(sent):
        return next((w for w in sent[:2] if _tok(w["word"]) in CTA_WORDS), None)
    ranked = [s_ for s_ in reversed(sentences[1:]) if opener(s_)] or \
        [s_ for s_ in reversed(sentences[1:]) if any(_tok(w["word"]) in CTA_WORDS for w in s_)
         and s_ is sentences[-1]]
    for sent in ranked[:1]:
        hit = opener(sent) or next(w for w in sent if _tok(w["word"]) in CTA_WORDS)
        if hit:
            effects.append({"type": "zoom", "start": _ts(sent[0]["start"] - pad),
                            "end": _ts(sent[-1]["end"] + pad), "scale": max(levels),
                            "center": list(focus)})
            effects.append({"type": "sfx", "sound": "ding", "at": _ts(hit["start"])})
            if intensity == "insane":
                effects.append({"type": "glitch", "start": _ts(sent[0]["start"]),
                                "end": _ts(sent[0]["start"] + Fraction(1, 5))})
            notes.append("CTA: %r gets the tightest framing + a ding on %r."
                         % (" ".join(w["word"] for w in sent)[:60], hit["word"]))
            break

    # Thin the sound effects: one hit roughly every 1.2 s at most, keeping the
    # important ones (hook impact, CTA ding) over decoration (whooshes, pops).
    priority = {"boom": 0, "bass_drop": 0, "ding": 1, "camera": 2, "pop": 3, "whoosh": 4}
    spacing = Fraction(6, 5) if intensity != "insane" else Fraction(4, 5)
    sfx = sorted((e for e in effects if e["type"] == "sfx"),
                 key=lambda e: (priority.get(e["sound"], 5), core.parse_time(e["at"])))
    kept_sfx = []
    for e in sfx:
        t = core.parse_time(e["at"])
        same_hit = [k for k in kept_sfx if abs(core.parse_time(k["at"]) - t) < Fraction(1, 20)]
        if same_hit or all(abs(core.parse_time(k["at"]) - t) >= spacing for k in kept_sfx):
            kept_sfx.append(e)
    dropped = len(sfx) - len(kept_sfx)
    effects = [e for e in effects if e["type"] != "sfx"] + kept_sfx
    if dropped:
        notes.append("Sound: thinned %d lower-priority effects to keep hits >= %.1fs apart."
                     % (dropped, float(spacing)))

    # 7. Finish.
    effects.append({"type": "color", "brightness": 0.02, "contrast": 1.08, "saturation": 1.16,
                    "gamma": 1.06})
    effects.append({"type": "captions", "source": "__WORDS__", "style": "viral"})
    if fmt == "short" and intensity != "clean":
        effects.append({"type": "progress_bar", "position": "top"})
        notes.append("Finish: progress bar (shows the viewer the end is near).")
    if music:
        effects.append({"type": "music", "file": music, "volume_db": -24, "duck": True,
                        "fade_in": 0.2, "fade_out": 0.6 if fmt == "long" else 0.0})
        notes.append("Music: bed at -24 dB, ducked under the voice.")
    if fmt == "long":
        effects.append({"type": "fade_out", "duration": 0.5})
    else:
        notes.append("Ending: hard cut on the last word, no fade, so the replay loops cleanly.")
    if intensity == "insane":
        notes.append("Taste check: insane pacing suits hype and entertainment; on a serious or "
                     "emotional topic it reads as noise. Use punchy there.")
    return cuts, effects, notes


def build_edl(source, words_path, intensity, fmt, music=None, hook=None, emphasis=(),
              focus=(0.5, 0.40), preset=None):
    words = core.load_words(words_path)
    cuts, effects, notes = plan_viral(source, words, intensity, fmt, music, hook, emphasis, focus)
    for e in effects:
        if e.get("source") == "__WORDS__":
            e["source"] = os.path.abspath(words_path)
    edl = {
        "source": os.path.abspath(source),
        "mode": "cut",
        "words": os.path.abspath(words_path),
        "segments": cuts,
        "transition": {"type": "cut"},
        "effects": effects,
        "output": {"preset": preset or ("youtube-shorts" if fmt == "short" else "youtube")},
        "audio": {"crossfade_ms": 8 if intensity != "clean" else 12,
                  "loudness": {"target_lufs": -14.0, "true_peak_db": -1.0, "lra": 11.0}},
        "viral": {"intensity": intensity, "format": fmt},
    }
    return edl, notes


def _sample(tmp):
    import json
    from media_analyzer import make_sample
    src = make_sample(tmp)
    words = [{"word": w, "start": a, "end": b} for w, a, b in [
        ("Stop", 0.30, 0.55), ("making", 0.58, 0.90), ("this", 0.92, 1.10), ("mistake.", 1.12, 1.70),
        ("Here", 3.30, 3.50), ("are", 3.52, 3.62), ("three", 3.64, 3.95), ("fixes", 3.97, 4.40),
        ("that", 4.42, 4.55), ("work.", 4.57, 4.95), ("Follow", 6.00, 6.35), ("for", 6.37, 6.50),
        ("more.", 6.52, 7.00)]]
    wp = os.path.join(tmp, "words.json")
    with open(wp, "w") as fh:
        json.dump(words, fh)
    return src, wp


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("source", nargs="?", help="source video")
    parser.add_argument("--words", help="word timestamps JSON (whisper / WhisperX / list)")
    parser.add_argument("--intensity", choices=sorted(INTENSITY), default="punchy")
    parser.add_argument("--format", choices=["short", "long"], default="short",
                        help="short = vertical reel/Short/TikTok; long = landscape YouTube")
    parser.add_argument("--preset", help="override the output preset")
    parser.add_argument("--music", help="music bed file (you must hold the licence)")
    parser.add_argument("--hook", help="hook title text (default: the first sentence)")
    parser.add_argument("--emphasis", default="", help="extra punch words, comma-separated")
    parser.add_argument("--focus", default="0.5,0.40",
                        help="zoom centre as x,y fractions (default 0.5,0.40: a face)")
    parser.add_argument("--edl-out", help="write the EDL here")
    parser.add_argument("--notes-out", help="write the editor's notes (markdown) here")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--sample", action="store_true", help="plan a synthetic clip")
    args = parser.parse_args()
    try:
        focus = tuple(float(v) for v in args.focus.split(","))
        if args.sample:
            with tempfile.TemporaryDirectory() as tmp:
                src, wp = _sample(tmp)
                edl, notes = build_edl(src, wp, args.intensity, args.format)
                edl["source"] = "<synthetic sample>"
        else:
            if not args.source or not args.words:
                parser.error("need a source video and --words (or --sample)")
            emphasis = [w for w in args.emphasis.split(",") if w.strip()]
            edl, notes = build_edl(args.source, args.words, args.intensity, args.format,
                                   args.music and os.path.abspath(args.music), args.hook,
                                   emphasis, focus, args.preset)
            if args.edl_out:
                core.write_json(edl, args.edl_out)
            if args.notes_out:
                with open(args.notes_out, "w", encoding="utf-8") as fh:
                    fh.write("# Editor's notes\n\n" + "\n".join("- " + n for n in notes) + "\n")
        if args.output == "json":
            print(core.write_json({"edl": edl, "notes": notes}))
        else:
            kinds = {}
            for e in edl["effects"]:
                kinds[e["type"]] = kinds.get(e["type"], 0) + 1
            print("viral plan (%s, %s): %d cuts, effects %s" % (
                args.intensity, args.format, len(edl["segments"]),
                ", ".join("%s×%d" % kv for kv in sorted(kinds.items()))))
            for n in notes:
                print("  - " + n)
            print("Next: edit_planner.py on the EDL, render, verify, then retention_audit.py.")
        return core.EXIT_OK
    except core.ToolError as exc:
        core.die(exc)


if __name__ == "__main__":
    sys.exit(main())
