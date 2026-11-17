#!/usr/bin/env python3
"""media_analyzer.py — measure a source video and propose a cut list.

Three subcommands, all read-only on the source:

  probe    Exact stream facts: rational fps, VFR/interlace/A-V-offset warnings,
           keyframe spacing (why stream-copy cuts land up to a GOP off).
  analyze  One decode pass: silences, black segments, scene changes, and
           integrated loudness / true peak / LRA (EBU R128).
  propose  Turn silences (and, with --words, filler words) into an editable
           EDL in `cut` mode with breathing-room padding. Never trims inside
           a word when word timestamps are supplied. Proposals only — a human
           or the agent reviews the EDL before edit_planner.py touches it.

Exit codes: 0 ok · 1 nothing to propose · 4 usage/input · 6 ffmpeg missing.

Examples:
  python3 media_analyzer.py probe raw.mp4
  python3 media_analyzer.py analyze raw.mp4 --output json > analysis.json
  python3 media_analyzer.py propose raw.mp4 --words words.json --edl-out edl.json
  python3 media_analyzer.py --sample      # self-contained demo on a synthetic clip
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

# Disfluencies that are almost never content. "like", "so", "you know" are
# deliberately absent: they carry meaning too often to cut without listening.
FILLERS = {"um", "umm", "uh", "uhh", "erm", "er", "ah", "ahh", "hmm", "mm", "mhm", "eh"}


def _num(text):
    return core.to_fraction(text)


def analyze(path, noise_db=-35.0, min_silence=0.5, scene=0.35, black=0.5):
    info = core.probe(path)
    ffmpeg, _ = core.require_ffmpeg()
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-v", "info", "-i", path]
    if info["video"]:
        cmd += ["-map", "0:v:0", "-vf",
                "scale=320:-2,blackdetect=d=%s:pix_th=0.10,select='gt(scene\\,%s)',showinfo"
                % (black, scene)]
    if info["audio"]:
        cmd += ["-map", "0:a:0", "-af",
                "silencedetect=n=%sdB:d=%s,ebur128=peak=true" % (noise_db, min_silence)]
    cmd += ["-f", "null", "-"]
    err = core.run(cmd).stderr.decode("utf-8", "replace")

    silences, start = [], None
    for line in err.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(Fraction(0), _num(m.group(1)))
            continue
        m = re.search(r"silence_end: (-?[\d.]+)", line)
        if m and start is not None:
            silences.append((start, _num(m.group(1))))
            start = None
    if start is not None:  # silence runs to end of file
        silences.append((start, core.to_fraction(info["duration"])))

    blacks = [(_num(a), _num(b)) for a, b in
              re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    scenes = [_num(t) for t in re.findall(r"\[Parsed_showinfo.*?pts_time:([\d.]+)", err)]

    loud = {}
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    for key, pat in (("integrated_lufs", r"I:\s+(-?[\d.]+) LUFS"),
                     ("lra_lu", r"LRA:\s+([\d.]+) LU"),
                     ("true_peak_dbtp", r"Peak:\s+(-?[\d.]+|-inf) dBFS")):
        m = re.search(pat, summary)
        if m:
            loud[key] = None if m.group(1) == "-inf" else float(m.group(1))

    kfs = core.keyframes(path) if info["video"] else []
    gaps = [b - a for a, b in zip(kfs, kfs[1:])]
    return {
        "source": info["path"],
        "probe": info,
        "silences": [{"start": core.fmt_ts(a, 6), "end": core.fmt_ts(b, 6),
                      "duration": core.fsec(b - a, 3)} for a, b in silences],
        "black_segments": [{"start": core.fmt_ts(a, 6), "end": core.fmt_ts(b, 6)}
                           for a, b in blacks],
        "scene_changes": [core.fmt_ts(t, 6) for t in scenes],
        "loudness": loud,
        "keyframes": {
            "count": len(kfs),
            "max_gap_s": core.fsec(max(gaps), 3) if gaps else None,
            "mean_gap_s": core.fsec(sum(gaps, Fraction(0)) / len(gaps), 3) if gaps else None,
            "note": "A stream-copy cut can only start on a keyframe, so it can land "
                    "up to max_gap_s early. The renderer re-encodes to cut on the exact frame.",
        },
        "params": {"noise_db": noise_db, "min_silence": min_silence,
                   "scene_threshold": scene, "black_min": black},
    }


def _overlapping_words(words, a, b):
    return [w for w in words if w["start"] < b and w["end"] > a]


def propose(path, words=None, noise_db=-35.0, min_silence=0.6, pad=0.15,
            min_cut=0.25, fillers=True):
    """Build a cut-mode EDL from silences (and filler words)."""
    result = analyze(path, noise_db=noise_db, min_silence=min_silence)
    duration = core.to_fraction(result["probe"]["duration"])
    pad_f, min_cut_f = core.to_fraction(pad), core.to_fraction(min_cut)
    cuts, notes = [], []

    for s in result["silences"]:
        a = core.parse_time(s["start"])
        b = core.parse_time(s["end"])
        # Keep `pad` of room at each edge, but never pad past the file edges.
        lo = a + pad_f if a > 0 else a
        hi = b - pad_f if b < duration else b
        if words:
            for w in _overlapping_words(words, lo, hi):
                # silencedetect mistook a quiet word for silence: shrink around it.
                if w["start"] - lo > hi - w["end"]:
                    hi = min(hi, w["start"] - pad_f)
                else:
                    lo = max(lo, w["end"] + pad_f)
            if _overlapping_words(words, lo, hi):
                notes.append("skipped silence at %s: words inside it" % s["start"])
                continue
        if hi - lo >= min_cut_f:
            cuts.append({"start": lo, "end": hi, "kind": "silence",
                         "reason": "silence %.2fs (padded %.2fs each side)" % (s["duration"], pad)})

    if words and fillers:
        for i, w in enumerate(words):
            token = re.sub(r"[^a-z]", "", w["word"].lower())
            if token not in FILLERS:
                continue
            prev_end = words[i - 1]["end"] if i else Fraction(0)
            next_start = words[i + 1]["start"] if i + 1 < len(words) else duration
            lo = max(prev_end, w["start"])
            # Take the pause after the filler too, leaving a natural 60 ms beat.
            hi = max(w["end"], next_start - Fraction(6, 100))
            cuts.append({"start": lo, "end": hi, "kind": "filler",
                         "reason": "filler word %r" % w["word"]})

    cuts.sort(key=lambda c: c["start"])
    merged = []
    for c in cuts:
        if merged and c["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
            merged[-1]["reason"] += " + " + c["reason"]
            merged[-1]["kind"] = "mixed" if merged[-1]["kind"] != c["kind"] else c["kind"]
        else:
            merged.append(dict(c))
    removed = sum((c["end"] - c["start"] for c in merged), Fraction(0))
    edl = {
        "version": 1,
        "source": result["source"],
        "mode": "cut",
        "segments": [{"start": core.fmt_ts(c["start"], 6), "end": core.fmt_ts(c["end"], 6),
                      "kind": c["kind"], "reason": c["reason"]} for c in merged],
        "audio": {"crossfade_ms": 12, "loudness": {"target_lufs": -14.0, "true_peak_db": -1.0,
                                                    "lra": 11.0}},
        "output": {"preset": "youtube-1080p"},
        "summary": {"cuts": len(merged), "removed_s": core.fsec(removed, 3),
                    "source_s": core.fsec(duration, 3),
                    "result_s": core.fsec(duration - removed, 3)},
        "notes": notes,
        "review": "PROPOSAL ONLY. Read every cut before planning; delete any that "
                  "remove a deliberate pause, a punchline beat, or content.",
    }
    if words:
        edl["words_used"] = True
    return edl, result


def make_sample(tmpdir):
    """Synthetic talking-head stand-in: frame-counter video + speech-like audio.

    The audio is noise shaped into ~3 syllables a second (aperiodic, so the
    verifier's cross-correlation has one unique answer) with two silent gaps.
    """
    ffmpeg, _ = core.require_ffmpeg()
    path = os.path.join(tmpdir, "sample.mp4")
    audio = ("aevalsrc='0.5*(random(0)*2-1)*(0.55+0.45*sin(2*PI*3.1*t))"
             "*(1-between(t,2,3.2))*(1-between(t,5,5.9))':s=48000:d=8")
    core.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
              "testsrc2=size=640x360:rate=30000/1001:duration=8", "-f", "lavfi", "-i", audio,
              "-c:v", "libx264", "-g", "60", "-pix_fmt", "yuv420p", "-c:a", "aac",
              "-shortest", path])
    return path


def print_text(cmd, data):
    if cmd == "probe":
        v, a = data.get("video"), data.get("audio")
        print("file: %s (%s)" % (data["path"], data["container"]))
        print("duration: %ss" % core.fsec(core.to_fraction(data["duration"]), 3))
        if v:
            print("video: %s %sx%s %s fps=%s (exact %s) frames~%s" % (
                v["codec"], v["width"], v["height"], v["pix_fmt"], v["fps_display"],
                v["fps"], v["frames_estimate"]))
        if a:
            print("audio: %s %s Hz %s ch" % (a["codec"], a["sample_rate"], a["channels"]))
        for w in data["warnings"]:
            print("WARNING " + w)
    elif cmd == "analyze":
        print("silences: %d · black: %d · scene changes: %d" % (
            len(data["silences"]), len(data["black_segments"]), len(data["scene_changes"])))
        print("loudness: %s" % data["loudness"])
        print("keyframes: %s" % {k: v for k, v in data["keyframes"].items() if k != "note"})
        for s in data["silences"][:40]:
            print("  silence %s -> %s (%.2fs)" % (s["start"], s["end"], s["duration"]))
    else:
        edl = data
        print("proposed cuts: %d  removes %.3fs of %.3fs -> %.3fs" % (
            edl["summary"]["cuts"], edl["summary"]["removed_s"], edl["summary"]["source_s"],
            edl["summary"]["result_s"]))
        for c in edl["segments"]:
            print("  CUT %s -> %s  [%s] %s" % (c["start"], c["end"], c["kind"], c["reason"]))
        for n in edl["notes"]:
            print("  note: " + n)
        print(edl["review"])


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Subcommands: probe | analyze | propose. See module docstring for examples.")
    parser.add_argument("command", nargs="?", choices=["probe", "analyze", "propose"])
    parser.add_argument("input", nargs="?", help="source media file")
    parser.add_argument("--words", help="word-level timestamps JSON (whisper/WhisperX/list)")
    parser.add_argument("--noise-db", type=float, default=-35.0,
                        help="silence threshold in dBFS (default -35; raise toward -30 for noisy rooms)")
    parser.add_argument("--min-silence", type=float, default=None,
                        help="shortest silence to detect, seconds (analyze 0.5, propose 0.6)")
    parser.add_argument("--pad", type=float, default=0.15,
                        help="seconds of silence kept at each side of a cut (default 0.15)")
    parser.add_argument("--min-cut", type=float, default=0.25,
                        help="drop proposed cuts shorter than this, seconds (default 0.25)")
    parser.add_argument("--no-fillers", action="store_true", help="do not propose filler-word cuts")
    parser.add_argument("--edl-out", help="write the proposed EDL here (propose)")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--sample", action="store_true",
                        help="generate a synthetic clip and run propose on it")
    args = parser.parse_args()

    try:
        if args.sample:
            with tempfile.TemporaryDirectory() as tmp:
                src = make_sample(tmp)
                edl, _ = propose(src, min_silence=0.6)
                edl["source"] = "<synthetic sample>"
                if args.output == "json":
                    print(core.write_json(edl))
                else:
                    print_text("propose", edl)
            return core.EXIT_OK
        if not args.command or not args.input:
            parser.error("need a subcommand and an input file (or --sample)")
        if args.command == "probe":
            data = core.probe(args.input)
            data["keyframe_count"] = len(core.keyframes(args.input)) if data["video"] else 0
        elif args.command == "analyze":
            data = analyze(args.input, noise_db=args.noise_db,
                           min_silence=args.min_silence or 0.5)
        else:
            words = core.load_words(args.words) if args.words else None
            data, _ = propose(args.input, words=words, noise_db=args.noise_db,
                              min_silence=args.min_silence or 0.6, pad=args.pad,
                              min_cut=args.min_cut, fillers=not args.no_fillers)
            if args.words:
                data["words"] = os.path.abspath(args.words)
            if args.edl_out:
                core.write_json(data, args.edl_out)
        if args.output == "json":
            print(core.write_json(data))
        else:
            print_text(args.command, data)
        if args.command == "propose" and not data["segments"]:
            return core.EXIT_FINDINGS
        return core.EXIT_OK
    except core.ToolError as exc:
        core.die(exc)


if __name__ == "__main__":
    sys.exit(main())
