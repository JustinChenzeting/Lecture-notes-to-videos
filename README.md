# lecture-notes-to-video

An [Agent Skill](https://agentskills.io) that turns lecture notes (typed or handwritten PDFs,
scans, phone photos, Markdown) into a narrated MP4 lecture: academic slides, animated
diagrams, a natural voice, exam-style checkpoint questions with a countdown, and
subtitles (`.srt`, `.vtt` and a track inside the MP4). The AI agent
writes one LaTeX file; the bundled scripts install everything they need and render the video.
Works with any agent that can run shell commands (Claude Code, Codex, Gemini CLI, Cursor, …).

**Install:** copy this folder into your agent's skills directory (e.g. `~/.claude/skills/`,
`~/.codex/skills/`, `.agents/skills/`), then ask: *"Make a 10-minute video from lecture5.pdf."*
Nothing else to install by hand. The first run sets itself up.

## Disk space (one-time, in `~/.cache/lecture-video`)

| Part | On disk |
|---|---|
| Private Python 3.12 + packages (TTS, PDF, imaging, ffmpeg) | ~360 MB |
| Offline Kokoro voices | ~125 MB |
| TinyTeX, **only if** no working LaTeX is installed | ~360 MB |
| **Total** | **~480 MB with your own LaTeX, ~850 MB without** (~350 MB download) |
| Optional voice cloning (`lv.py setup --clone`) | +2–4 GB |
| Audio cache, grows with use | ~3 MB per minute of video |

No admin rights needed. Uninstall by deleting that folder.

## Time

| Step | Typical |
|---|---|
| First-run setup | ~3 min measured on a fast connection; allow up to 10 |
| Agent reads the notes and writes the slides (10-min lecture) | 10–30 min, depending on the model and the notes |
| Check + render (10-min video, default online voice) | 1–3 min; offline voice +3 min; cloned voice 20–60 min |
| Re-render after an edit | seconds (unchanged lines come from the audio cache) |
| Subtitles | free: generated from the narration during the render, no extra tokens or time |

## Token cost (per 10-minute lecture, estimated)

- **Written by the agent:** ~5–9k tokens of LaTeX + narration (measured on real 10-min
  lectures), plus a few thousand for transcripts, fixes and the report: **~15–30k output tokens**.
- **Read by the agent:** skill instructions ~4k, notes ~2–10k, page images ~1.5k each,
  slide contact sheets ~1.5k each (5–7 per lecture): **~30–70k tokens of new input**.
- Agents resend their context on every step, so the total billed input is usually several
  hundred thousand tokens, mostly cheap cached reads. Shorter videos cost proportionally less.
  Rendering itself uses free local tools and costs no tokens.

## More
- How the agent uses it: [SKILL.md](SKILL.md)
- Personal logo, colours, voices, folders: [references/customization.md](references/customization.md)
- Voices and cloning: [references/voices.md](references/voices.md)
- Setup problems, offline use, Windows: [references/troubleshooting.md](references/troubleshooting.md)

Tested on macOS (Apple silicon) and Ubuntu 24.04; Windows support is written but untested.

License: MIT, see [LICENSE](LICENSE). The bundled tools it downloads (TinyTeX, Kokoro,
ffmpeg, Python packages) keep their own licenses.
