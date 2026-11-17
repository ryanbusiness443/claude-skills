# Workspace and inputs: getting footage in at any size, and edits back out

A chat upload has a size limit; video files do not. This is how footage reaches the editor without
re-encoding or splitting, what each route costs, and how the finished file gets back. 🟢 tested
in this skill's own runs · 🟡 documented by the service, not re-tested here.

## 1. Routes in, best first

| Route | Size limit | How | Notes |
|---|---|---|---|
| **Google Drive** | none found (1.27 GB file listed, 35 MB downloaded in 2.4 s) 🟢 | Drive connector finds the file; download from `drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t` | The connector's own download returns base64 into the chat, so use it for metadata only, never for video |
| **Local Claude Code** | your disk | run the skill on your own machine, point it at the file | no transfer at all; the fastest route for daily use |
| **Descript** | plan-dependent 🟡 | `import_media` (direct upload or URL), edit, `publish_project`, download | free plan exports carry a watermark; transcripts come for free |
| **Dropbox / any direct link** | none 🟢 | a share link with `?dl=1` | the link must be a file, not a preview page |
| **Chat upload** | small | attach the file | fine for clips under ~30 MB |

**Never** re-encode a source before editing to make it fit. Every generation loses quality, and
the frame-exact plan is built on the file you give it. If a route has a limit, use another route.

## 2. Routes out

| Route | How |
|---|---|
| **This chat** | the finished MP4 is sent as a file |
| **Google Drive** | upload into an `Edited/` folder (ask before writing to the user's Drive) |
| **Descript** | import the render as a new project for review; share links stay private by default |
| **YouTube, Instagram, TikTok** | never upload or schedule without an explicit request for that post |

## 3. The workspace (what the editor needs installed)

| Tool | Why | Install |
|---|---|---|
| ffmpeg ≥ 5.1 | every cut, effect and check | `brew install ffmpeg` · `sudo apt install ffmpeg` |
| faster-whisper | word timestamps (captions, word-safe cuts, the viral planner) | `pip install faster-whisper` |
| OpenFilm CLI | CC0 music, sounds and grades (`asset_packs.py`) | `npm i -g openfilm` |
| A heavy font | hook and caption text (Montserrat/Inter Black, Anton...) | any OS font; `fc-match` finds it |

Check with `python3 scripts/asset_packs.py --sample`. It reports the LUT maths and how many
library items it can see. In a Claude Code cloud environment, put the installs in the
environment's setup script so every new session starts ready.

## 4. A full round trip

```bash
# 1. in: Drive file id from the Drive connector's search
curl -sSL -o raw.mp4 "https://drive.usercontent.google.com/download?id=$ID&export=download&confirm=t"
# 2. transcribe, plan, render, verify (see SKILL.md)
# 3. out: send the MP4 back; on request, also to Drive or Descript
```

A private file downloads only when the session can reach it. If the download returns an HTML
sign-in page instead of video (check: `ffprobe raw.mp4` fails), set the file to "anyone with the
link" for the transfer and back to private afterwards. Do this only with the owner's go-ahead.

## Sources

1. Google Drive API, "Download and export files" (files.get with alt=media; the
   usercontent download host for shared files).
2. Google Drive Help, "Share files from Google Drive" (link sharing and restricting it again).
3. Descript Help, "Importing media" and "Publishing and exporting" (plan limits, watermark).
4. Dropbox Help, "Force a download with dl=1".
5. FFmpeg documentation, `ffprobe` (detecting a non-media download).
6. SYSTRAN, faster-whisper README: word-level timestamps.
7. OpenFilm README (github.com/openfilm/openfilm): `npm i -g openfilm`, the `get` library verbs.
