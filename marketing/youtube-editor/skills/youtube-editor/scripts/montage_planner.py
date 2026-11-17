#!/usr/bin/env python3
"""montage_planner.py — cut a pile of clips to the music: every cut on a beat.

For B-roll edits with no talking: day-in-my-life vlogs, motivation montages,
story sequences, travel and event recaps. Two steps, both deterministic:

  1. bind     conform every clip to one size and frame rate (fill-crop, never
              stretch) and join them into one source file with an index, so the
              frame-exact single-source engine (planner, renderer, verifier)
              handles a multi-clip edit unchanged. Clip audio is kept at
              --ambient-db (default -30 dB: room tone under the music) or muted.
  2. plan     detect the music's beats (beat_detector.py), lay shots on them
              (shots per beat by style and section: faster in rises, longer in
              drops), take each shot from the middle of its clip, add the
              style's moves, and write an ordinary EDL with a beat_sync record
              the verifier checks (BEAT_SYNC: cuts on the beat, music in place).

Styles:
  day-in-life    2 beats a shot, clips in your order (chronological), a time or
                 label card on each new clip, shutter click on clip changes, warm
                 grade, light grain
  motivation     2 beats a shot, 1 in rises; flash + impact on downbeat cuts in
                 rises, shake on the biggest hit, --text lines as centre quotes on
                 downbeats, teal-orange, bars on landscape
  storytelling   4 beats a shot (downbeats), slow push-ins, moody grade, quotes
                 as lower lines, fade out

Shot length is quantised to frames; a cut lands on the frame nearest its beat,
so the worst offset is half a frame (16.7 ms at 30 fps), which the verifier
checks for every cut.

Exit codes: 0 ok · 4 usage/input · 6 ffmpeg missing.

Examples:
  python3 montage_planner.py clips/*.mp4 --music track.mp3 --style day-in-life \\
      --labels "7:00 AM,8:30 AM,NOON,6:00 PM" --bound-out bound.mp4 --edl-out vlog.edl.json
  python3 montage_planner.py broll/ --music epic.mp3 --style motivation --format long \\
      --text "DISCIPLINE|BEATS|MOTIVATION" --length 30 --pack pack.json --edl-out m.edl.json
  python3 montage_planner.py --sample
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ytedit_core as core  # noqa: E402

VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts")
STYLES = {
    "day-in-life": {"beats": 2, "rise_beats": 2, "grade": "warm-vlog",
                    "look": {"grain": 3, "vignette": 0.2}},
    "motivation": {"beats": 2, "rise_beats": 1, "grade": "teal-orange",
                   "look": {"grain": 6, "vignette": 0.35}, "letterbox_long": 2.0},
    "storytelling": {"beats": 4, "rise_beats": 2, "grade": "moody",
                     "look": {"grain": 8, "vignette": 0.45}},
}
FORMATS = {"short": ((1080, 1920), "youtube-shorts"), "long": ((1920, 1080), "youtube")}


def find_clips(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(os.path.join(p, f) for f in os.listdir(p)
                          if f.lower().endswith(VIDEO_EXT))
        elif os.path.isfile(p):
            out.append(p)
        else:
            raise core.ToolError("not found: %s" % p)
    if len(out) < 2:
        raise core.ToolError("a montage needs at least 2 clips")
    return out


def bind_clips(clips, out_path, size, fps, ambient_db=-30.0):
    """Conform + join; returns the index [{file, start, frames, duration, label}]."""
    ffmpeg, _ = core.require_ffmpeg()
    W, H = size
    inputs, graph, index, pos = [], [], [], 0
    for i, c in enumerate(clips):
        info = core.probe(c)
        dur = core.to_fraction(info["duration"])
        frames = int(dur * fps) - 1  # one frame short of the end: no partial frame
        if frames < int(fps):
            raise core.ToolError("clip shorter than a second: %s" % c)
        inputs += ["-i", c]
        graph.append("[%d:v:0]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                     "setsar=1,fps=%s,trim=end_frame=%d,setpts=PTS-STARTPTS,format=yuv420p[v%d]"
                     % (i, W, H, W, H, core.frac_str(fps), frames, i))
        secs = core.fsec(Fraction(frames) / fps, 6)
        if info.get("audio") and ambient_db is not None:
            graph.append("[%d:a:0]aresample=48000,aformat=channel_layouts=stereo,"
                         "volume=%.1fdB,apad,atrim=end=%s,asetpts=PTS-STARTPTS[a%d]"
                         % (i, ambient_db, secs, i))
        else:
            graph.append("anullsrc=r=48000:cl=stereo,atrim=end=%s[a%d]" % (secs, i))
        index.append({"file": os.path.abspath(c), "label": os.path.splitext(os.path.basename(c))[0],
                      "start_frame": pos, "frames": frames,
                      "start": core.frac_str(Fraction(pos) / fps),
                      "creation_time": (info.get("tags") or {}).get("creation_time")})
        pos += frames
    graph.append("".join("[v%d][a%d]" % (i, i) for i in range(len(clips)))
                 + "concat=n=%d:v=1:a=1[v][a]" % len(clips))
    core.run([ffmpeg, "-v", "error", "-y", "-nostdin"] + inputs +
             ["-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-g", str(int(fps)),
              "-r", core.frac_str(fps), "-c:a", "pcm_s16le" if out_path.endswith(".mov") else "aac",
              "-b:a", "320k", "-movflags", "+faststart", out_path])
    return index


def _clock(ts):
    """'2026-10-31T10:48:48.000000Z' -> '10:48 AM' (the camera's clock, as recorded)."""
    try:
        hh, mm = int(ts[11:13]), int(ts[14:16])
    except (TypeError, ValueError):
        return None
    return "%d:%02d %s" % (hh % 12 or 12, mm, "AM" if hh < 12 else "PM")


def shot_grid(beats, length, style, sections):
    """Cut times (seconds) on beats: shots of N beats, fewer in rises."""
    cfg = STYLES[style]
    rises = []
    for i, sct in enumerate(sections):
        if sct.get("change") == "rise":
            end = next((x["start"] for x in sections[i + 1:] if x.get("change") == "drop"), 1e9)
            rises.append((sct["start"], end))
    cuts, k = [], 0
    usable = [b for b in beats if 0 < b < length - 0.5]
    while k < len(usable):
        t = usable[k]
        if not cuts or t - cuts[-1] > 0.3:
            cuts.append(t)
        in_rise = any(a <= t < b for a, b in rises)
        k += cfg["rise_beats"] if in_rise else cfg["beats"]
    return cuts, rises


def plan_montage(index, bound, music, beats_rep, style="day-in-life", fmt="short",
                 length=None, labels=None, texts=(), fps=Fraction(30)):
    cfg = STYLES[style]
    notes, effects, segs = [], [], []
    beats = beats_rep["beats"]
    downbeats = set(round(b, 4) for b in beats_rep.get("downbeats", []))
    total_src = sum(c["frames"] for c in index) / float(fps)
    music_len = core.to_fraction(core.probe(music)["duration"])
    length = float(length or min(float(music_len), 60.0 if fmt == "short" else 180.0))
    length = min(length, float(music_len))
    cuts, rises = shot_grid(beats, length, style, beats_rep.get("sections", []))
    # the edit ends on the last beat at or before the length (a clean ending)
    end = max([b for b in beats if b <= length] or [length])
    cuts = [c for c in cuts if c < end - 0.3]
    bounds = [0.0] + cuts + [end]
    notes.append("Music: %s at %.1f BPM (confidence %.2f); %d shots on the beat over %.1fs."
                 % (os.path.basename(music), beats_rep["tempo_bpm"], beats_rep["confidence"],
                    len(bounds) - 1, end))
    if beats_rep["confidence"] < 0.3:
        notes.append("Warning: the beat is weak or irregular; cuts follow the detected grid, "
                     "check by ear (or pass the tempo: beat_detector.py --bpm).")
    # assign shots: clips in order, round-robin; each shot from the middle of the
    # clip's unused material, never reusing a frame
    cursor = {i: 0.2 for i in range(len(index))}
    order = list(range(len(index)))
    shot_clip = []
    reused = 0
    # quantise in frames once: cut k lands on frame round(beat_k * fps), and each
    # shot is exactly the frames between two cuts, so nothing drifts
    fb = [int(round(Fraction(str(x)) * fps)) for x in bounds]
    for n, (a, b) in enumerate(zip(bounds, bounds[1:])):
        nfr = fb[n + 1] - fb[n]
        need = nfr / float(fps)
        for tries in range(len(order)):
            ci = order[(n + tries) % len(order)]
            c = index[ci]
            clen = c["frames"] / float(fps)
            start = cursor[ci]
            if n < len(order) and clen > need + 0.4:
                start = max(start, (clen - need) / 2.0 - need)  # first visit: near the middle
            if start + need <= clen - 0.1:
                break
        else:
            # every clip is used up at this point: reuse the longest one from the top
            # (editors do), and say so
            ci = max(order, key=lambda i: index[i]["frames"])
            c = index[ci]
            clen = c["frames"] / float(fps)
            if need > clen - 0.3:
                raise core.ToolError("a %.2fs shot is longer than every clip; slow the pace "
                                     "(--style storytelling) or add longer clips" % need)
            start = 0.2
            reused += 1
        cursor[ci] = start + need + 0.05
        f0 = c["start_frame"] + int(start * float(fps))
        segs.append({"start": "%df" % f0, "end": "%df" % (f0 + nfr),
                     "label": "shot %d: %s (beat %.3fs)" % (n + 1, c["label"], a)})
        shot_clip.append(ci)
    if reused:
        notes.append("Footage: %d shots reuse material already shown (%.1fs of clips for a "
                     "%.1fs edit). More clips, or a shorter --length, avoid repeats."
                     % (reused, total_src, end))
    # the bound file is in clip order; shots revisit clips, so keep order is deliberate
    effects.append({"type": "music", "file": os.path.abspath(music), "volume_db": -3,
                    "duck": False, "fade_in": 0.0, "fade_out": 1.5 if style != "motivation" else 0.6})
    seen = set()
    for n, (a, ci) in enumerate(zip(bounds, shot_clip)):
        is_down = round(a, 4) in downbeats
        if style == "day-in-life" and ci not in seen:
            seen.add(ci)
            lab = (labels[ci] if labels and ci < len(labels) else
                   _clock(index[ci].get("creation_time")))
            if lab:
                effects.append({"type": "text", "start": "%.4f" % a,
                                "end": "%.4f" % min(a + 1.6, bounds[n + 1]), "text": lab.upper(),
                                "position": "top", "style": "box", "size": 0.035, "time": "output"})
            if n:
                effects.append({"type": "sfx", "sound": "camera", "at": "%.4f" % a,
                                "time": "output"})
        if style == "motivation" and n and is_down and any(r0 <= a < r1 for r0, r1 in rises):
            effects.append({"type": "flash", "start": "%.4f" % a, "end": "%.4f" % (a + 0.15),
                            "peak": 0.55, "time": "output"})
            effects.append({"type": "sfx", "sound": "boom", "at": "%.4f" % a, "time": "output"})
        if style == "storytelling" and n % 2 == 0:
            effects.append({"type": "zoom", "start": "%.4f" % a,
                            "end": "%.4f" % bounds[n + 1], "scale": 1.08, "center": [0.5, 0.5],
                            "time": "output"})
    if style == "motivation" and rises:
        r0 = next((b for b in beats if b >= rises[0][0]), None)
        if r0 is not None and r0 < end - 1:
            effects.append({"type": "shake", "start": "%.4f" % r0, "end": "%.4f" % (r0 + 0.35),
                            "intensity": 0.012, "time": "output"})
            notes.append("Motivation: shake + flashes where the music rises (%.1fs)." % r0)
    if texts:
        downs = [b for b in sorted(downbeats) if 1.0 <= b < end - 2.0] or bounds[1:-1]
        step = max(1, len(downs) // (len(texts) + 1))
        placed = 0
        for j, line in enumerate(texts):
            k = (j + 1) * step
            if k >= len(downs):
                break
            a = downs[k]
            b = next((x for x in downs if x > a + 1.5), a + 2.0)
            effects.append({"type": "text", "start": "%.4f" % a, "end": "%.4f" % min(b, end),
                            "text": line.upper(), "time": "output",
                            "position": "center" if style == "motivation" else "bottom",
                            "style": "hook" if style == "motivation" else "outline",
                            "size": 0.05 if fmt == "short" else 0.07})
            placed += 1
        notes.append("Text: %d of %d lines on downbeats%s." % (
            placed, len(texts), "" if placed == len(texts) else " (the rest did not fit; "
            "lengthen the edit or cut lines)"))
    look = dict(cfg["look"])
    if fmt == "long" and cfg.get("letterbox_long"):
        look["letterbox"] = cfg["letterbox_long"]
    effects.append(dict({"type": "look"}, **look))
    if style == "storytelling":
        effects.append({"type": "fade_out", "duration": 1.0})
    edl = {"source": os.path.abspath(bound), "mode": "keep", "allow_reorder": True,
           "segments": segs, "transition": {"type": "cut"}, "effects": effects,
           "output": {"preset": FORMATS[fmt][1]},
           "audio": {"crossfade_ms": 4,
                     "loudness": {"target_lufs": -14.0, "true_peak_db": -1.0, "lra": 11.0}},
           "beat_sync": {"music": os.path.abspath(music), "music_start": 0,
                         "beats": [b for b in beats if b <= end + 1], "all_cuts_on_beat": True},
           "montage": {"style": style, "format": fmt, "clips": index}}
    return edl, notes


def run(clips, music, style, fmt, bound_out, length=None, labels=None, texts=(), beats=None,
        bpm=None, pack=None, pack_dir=None, ambient_db=-30.0, fps=Fraction(30)):
    import asset_packs
    import beat_detector
    from viral_planner import apply_pack
    size = FORMATS[fmt][0]
    index = bind_clips(clips, bound_out, size, fps, ambient_db)
    rep = core.load_json(beats) if beats else beat_detector.detect(music, bpm=bpm)
    edl, notes = plan_montage(index, bound_out, music, rep, style, fmt, length, labels, texts, fps)
    if pack is not None:
        pack = asset_packs.load_pack(pack)
    apply_pack(edl["effects"], style, pack,
               pack_dir or os.path.join(os.path.dirname(os.path.abspath(bound_out)),
                                        "pack-" + style), notes)
    return edl, notes


def _sample(tmp):
    """Four 3-second coloured clips and a 120 BPM click track."""
    ffmpeg, _ = core.require_ffmpeg()
    import beat_detector
    clips = []
    for i in range(4):
        p = os.path.join(tmp, "clip%d.mp4" % i)
        core.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                  "testsrc2=s=640x360:r=30:d=3,hue=h=%d" % (i * 90), "-f", "lavfi", "-i",
                  "sine=f=%d:d=3" % (300 + 100 * i), "-shortest", "-c:v", "libx264",
                  "-pix_fmt", "yuv420p", "-c:a", "aac", p])
        clips.append(p)
    music, _ = beat_detector._sample(tmp, secs=8.0)
    return clips, music


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("clips", nargs="*", help="clip files or folders (in story order)")
    parser.add_argument("--music", help="the music (you hold its licence, or an OpenFilm track)")
    parser.add_argument("--style", choices=sorted(STYLES), default="day-in-life")
    parser.add_argument("--format", choices=sorted(FORMATS), default="short")
    parser.add_argument("--length", type=float, help="target seconds (ends on a beat)")
    parser.add_argument("--labels", help="day-in-life cards per clip, comma-separated")
    parser.add_argument("--text", default="", help="quote lines, separated by |")
    parser.add_argument("--beats", help="beats JSON (default: detect from --music)")
    parser.add_argument("--bpm", type=float, help="known tempo of the music")
    parser.add_argument("--pack", help="pack.json from asset_packs.py (library sounds + grade)")
    parser.add_argument("--ambient-db", type=float, default=-30.0,
                        help="clip sound under the music (dB); use --mute-clips for silence")
    parser.add_argument("--mute-clips", action="store_true")
    parser.add_argument("--fps", default="30")
    parser.add_argument("--bound-out", help="where to write the joined source (required)")
    parser.add_argument("--edl-out", help="write the EDL here")
    parser.add_argument("--notes-out", help="write the editor's notes here")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--sample", action="store_true", help="plan a synthetic montage")
    args = parser.parse_args()
    try:
        fps = core.to_fraction(args.fps)
        texts = [t.strip() for t in args.text.split("|") if t.strip()]
        labels = [t.strip() for t in args.labels.split(",")] if args.labels else None
        if args.sample:
            with tempfile.TemporaryDirectory() as tmp:
                clips, music = _sample(tmp)
                edl, notes = run(clips, music, args.style, "long", os.path.join(tmp, "bound.mp4"),
                                 texts=texts, pack_dir=os.path.join(tmp, "pack"), fps=fps)
                edl["source"] = "<synthetic bound clips>"
        else:
            if not args.clips or not args.music or not args.bound_out:
                parser.error("need clips, --music and --bound-out (or --sample)")
            edl, notes = run(find_clips(args.clips), args.music, args.style, args.format,
                             args.bound_out, args.length, labels, texts, args.beats, args.bpm,
                             args.pack, None, None if args.mute_clips else args.ambient_db, fps)
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
            print("montage (%s): %d shots from %d clips, effects %s" % (
                args.style, len(edl["segments"]), len(edl["montage"]["clips"]),
                ", ".join("%s×%d" % kv for kv in sorted(kinds.items()))))
            for n in notes:
                print("  - " + n)
            print("Next: edit_planner.py on the EDL, render, verify (BEAT_SYNC checks the cuts).")
        return core.EXIT_OK
    except core.ToolError as exc:
        core.die(exc)


if __name__ == "__main__":
    sys.exit(main())
