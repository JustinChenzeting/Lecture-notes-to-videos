# lecture-notes-to-video

An [Agent Skill](https://agentskills.io) that turns lecture notes (typed or handwritten PDFs,
scans, phone photos, Markdown) into a narrated MP4 lecture: academic slides, animated
diagrams, a natural voice, actual homework questions with pause-and-work prompts, short recall exercises, and
subtitles (`.srt`, `.vtt` and a track inside the MP4). English or Chinese: Chinese notes, or a
request for a Chinese video, give Mandarin narration, Chinese slides and Chinese subtitles. On first
use the agent asks once for your logo and a name (a university, course or channel) to put on the
slides, or none; the answer is remembered. For each lecture it also asks **Basic or Elaborated**
visuals:
- **Basic**: slides that teach the way Khan Academy and Brilliant do: the concrete picture first,
  one colour per idea, labels hand-written as they are spoken, a pointer, camera zooms, parameter
  sliders, soft fades.
- **Elaborated**: Basic plus full-screen animated scenes at 1080p, timed beat by beat to the
  narration and built from tested parts: the Manim API in the browser (manim-web) for maths,
  ready-made blocks for manipulatives, sliders and physics (pendulums, springs, projectiles,
  matter.js and cannon-es collisions), quantum mechanics (wave packets, tunnelling, the double
  slit, stationary states; methods from marl0ny's QM-Simulator-1D and -2D), materials science
  built on matterviz (phase diagrams with the lever rule, crystal structures and Miller planes,
  dislocations and Burgers circuits) with 3Dmol.js and SmilesDrawer for molecules, and three.js for 3D.

The AI agent writes one LaTeX video source, an exercise-source plan, and separate recall
questions and answers (plus scene pages for Elaborated); the bundled scripts render the video. Sample of Elaborated scenes (silent,
55 s): [assets/samples/elaborated-preview.mp4](assets/samples/elaborated-preview.mp4): place-value
blocks with camera zooms and a colour-coded sum, a "predict" slider sweep, a sliced 3D surface,
and a projectile simulation.
Works with any agent that can run shell commands (Claude Code, Codex, Gemini CLI, Cursor, …).

**Install:** copy this folder into your agent's skills directory (e.g. `~/.claude/skills/`,
`~/.codex/skills/`, `.agents/skills/`), then ask: *"Make a 10-minute video from lecture5.pdf."*
Nothing else to install by hand. The first run sets itself up.

## Learning workflow (2026-11-01)

Adopted at the user's request after the explanations and demonstrations were useful but
retention remained weak: ask for the actual homework at generation time, preserve its
difficulty, require a pause-and-work attempt before feedback, add still moments that connect
ideas, and deliver recall questions with separate answers for later review. This supersedes
the five-second countdown as the default for new retrieval questions. Legacy `\examq` still
works; `\attemptq` provides the new three-page question/hold/solution sequence. MP4 pause is
manual, and suggested problem-solving time is additional to video runtime.

Narration now uses short, explicit reasoning steps tied to visible quantities, with a spoken
clarity check. The research, practical defaults and examples are in
[references/learning-design.md](references/learning-design.md). Both skill copies carry this
method; their existing platform, branding and voice differences remain. Time/token figures
below are historical measurements from before this revision, not new benchmarks.

## Disk space (one-time, in `~/.cache/lecture-video`)

| Part | On disk |
|---|---|
| Private Python 3.12 + packages (TTS, PDF, imaging, ffmpeg) | ~360 MB |
| Offline Kokoro voices | ~125 MB |
| TinyTeX, **only if** no working LaTeX is installed | ~360 MB |
| **Total** | **~480 MB with your own LaTeX, ~850 MB without** (~350 MB download) |
| Chinese slide fonts (Noto Serif/Sans SC), fetched by the first Chinese lecture | +40 MB |
| Optional offline Chinese voice (`lv.py setup --zh`) | +270 MB |
| Optional voice cloning (`lv.py setup --clone`) | +2–4 GB |
| Elaborated visuals: scene libraries (three.js, anime.js, matter.js, KaTeX), first elaborated lecture | +3 MB |
| … plus manim-web (the Manim API), cannon-es (3D physics), 3Dmol.js and SmilesDrawer (molecules), only when a scene uses them | +10 MB (4 MB download) |
| Elaborated visuals on a computer with no Chrome or Edge: Google's headless Chrome | +200 MB (104–126 MB download) |
| Audio cache, grows with use | ~3 MB per minute of video |

No admin rights needed. Uninstall by deleting that folder.

## Time

**Estimated working time for a 10-minute video** (agent work plus rendering, after the one-time
setup; Claude Opus-class model, typed notes):

| | Basic | Elaborated (4–6 scenes) |
|---|---|---|
| Agent reads the notes, writes slides (and scenes), checks them | 20–35 min | 35–65 min, typically ~45 |
| Render (default online voice) | 1–3 min | 3–8 min |
| **Total** | **~25–40 min** | **~40–70 min** |

How the estimate is made: on short test videos the agent spent ~5–6 min on fixed steps (reading
the skill, ingesting, checking, rendering, reporting) and 1.5–2.5 min of writing per minute of
video; each animated scene written by hand added ~6 min, and with the building blocks and
examples a scene is expected to take 3–5 min (custom scenes still ~6–10). Handwritten notes add
the time to transcribe them; long derivations and many checkpoints sit at the top of the range.

Per step:

| Step | Basic | Elaborated |
|---|---|---|
| First-run setup | ~3 min on a fast connection; allow up to 10 | + a few seconds for the scene libraries |
| Agent reads the notes and writes the slides (10-min lecture) | 20–35 min, depending on the model and the notes | 35–65 min: + 3–5 min per scene built from blocks or an example, 6–10 per custom scene |
| Check + render (10-min video, default online voice) | 1–3 min; offline voice +3 min; cloned voice 20–60 min | + about 1 s per second of scene (1080p), so +2–5 min |
| Re-render after an edit | seconds (unchanged lines come from the audio cache) | seconds, plus the changed scenes (frames are cached) |
| Subtitles | free: generated from the narration during the render, no extra tokens or time | same |

Measured on 1.5–2-minute test videos (Claude Opus, October 2026): Basic took 9 min of agent time
(1 min of it running tools) against 7.5 min for the plain slides of the previous version;
Elaborated, with scenes still written by hand, took about 21 min with one or two scenes (3 min of
it running tools: the rest is writing and fixing scene code, which the building blocks now cut).
Rendering a 1-minute lecture with a 32-second scene took 46 s on an Apple M5.

## Token cost (per 10-minute lecture, estimated)

- **Written by the agent:** ~5–9k tokens of LaTeX + narration (measured on real 10-min
  lectures), plus a few thousand for transcripts, fixes and the report: **~15–30k output tokens**.
- **Read by the agent:** skill instructions ~4k, notes ~2–10k, page images ~1.5k each,
  slide contact sheets ~1.5k each (5–7 per lecture): **~30–70k tokens of new input**.
- Agents resend their context on every step, so the total billed input is usually several
  hundred thousand tokens, mostly cheap cached reads. Shorter videos cost proportionally less.
  Rendering itself uses free local tools and costs no tokens.
- **Basic visuals** cost about the same: +5% (measured 119k vs 113k tokens of peak context on a
  1.5-minute video), for the visual-style guide and the hand-written labels and zooms.
- **Elaborated visuals** cost about 1.7× Basic when scenes are written by hand (measured ~205k
  tokens of peak context on a 2-minute video with 1–2 scenes): each such scene is ~100–200 lines
  of code (~2–4k output tokens) plus the scene guide (~6k) and its contact sheets (~1.5k each).
  Built from the blocks and examples, a scene is ~40–80 lines, so expect ~1.4–1.6× Basic. For a
  10-minute lecture with 4–6 scenes: roughly **+15–30k output tokens and +40–70k new input** over Basic.

## More
- How the agent uses it: [SKILL.md](SKILL.md)
- Teaching visuals (Basic): [references/visual-style.md](references/visual-style.md); animated scenes (Elaborated): [references/scenes.md](references/scenes.md)
- Personal logo, colours, voices, folders: [references/customization.md](references/customization.md)
- Voices and cloning: [references/voices.md](references/voices.md)
- Chinese lectures: [references/chinese.md](references/chinese.md)
- Setup problems, offline use, Windows: [references/troubleshooting.md](references/troubleshooting.md)

Tested on macOS (Apple silicon) and Ubuntu 24.04; Windows support is written but untested.

License: MIT, see [LICENSE](LICENSE). The bundled tools it downloads (TinyTeX, Kokoro,
ffmpeg, Python packages, and for scenes three.js, anime.js, matter.js, cannon-es, KaTeX, manim-web, SmilesDrawer (MIT), 3Dmol.js (BSD-3) and the bundled matterviz core and data (MIT, `assets/scenes/vendor/`)) keep
their own licenses. Scene look partly adapted from ThreeUI (github.com/MengTo/threeui, MIT).
