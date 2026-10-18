---
name: lecture-notes-to-video
description: Turn lecture notes (typed or handwritten PDFs, scans, phone photos, Markdown) into a narrated lecture video (MP4) with clean academic slides, step-by-step animated diagrams, a natural British narrator, and exam-style checkpoint questions that pause with a countdown before revealing the answer. Self-installing and fully automated - one script sets up Python, LaTeX, ffmpeg and offline voices on macOS, Linux or Windows, then renders the video. Use this whenever the user wants a lecture, notes, slides, handout, chapter or problem set turned into a video, a narrated walkthrough, a "lecture recording", an explainer with visuals, or a study video to watch or revise from - even if they just say "make this into a video" or "explain lecture 5 to me as a video".
license: MIT (see LICENSE)
compatibility: Needs a shell, Python 3.8+ and internet on first run (downloads about 300 MB into a user cache - Python packages, offline voices, ffmpeg, and TinyTeX when no LaTeX is installed). Tested on macOS and Linux; Windows support is untested. Image viewing is needed for handwritten notes and recommended for checking slides.
metadata:
  version: "2.0.0"
---

# Lecture notes → narrated lecture video

You write exactly one file: a beamer `lecture.tex` holding the slides, diagrams and narration
together. The bundled scripts do everything else (install, LaTeX → PNG pages → text-to-speech
→ ffmpeg → MP4), so the cost is about one long answer per lecture, and later edits
re-synthesize only the lines that changed.

## Quick start: the whole pipeline

Every step is one command: `python3 <skill-dir>/scripts/lv.py <command>`, where `<skill-dir>`
is the absolute path of the folder containing this file (on Windows use `py -3` instead of
`python3`). Below, `lv` is shorthand for that whole command; write it out in full each time,
because shell variables usually do not persist between your commands.

```bash
lv setup                           # 0. one-time install; give it a 10-minute timeout or run it in the background
lv init PHYS101-L05                # 1. prints the work folder (WORK) and copies the template into it
lv ingest notes.pdf --out WORK     #    any mix of .pdf .png .jpg .heic .md .txt; several files are fine
#                                       read the notes (§1), plan (§2), write WORK/lecture.tex (§3-4)
lv check WORK/lecture.tex          # 2. compile + numbered contact sheets + layout warnings, no audio
lv render WORK/lecture.tex         # 3. -> WORK/PHYS101-L05.mp4 (or give an output path)
```

- **Step 0 installs everything** (uv, a private Python 3.12, TinyTeX only when no working LaTeX
  exists, ffmpeg, Kokoro voices) into a per-user cache: about 3 minutes on a fast connection,
  up to 10 on a slow one, with no administrator rights needed. It is idempotent: when it is
  already done it finishes in seconds, and if it is interrupted, running it again resumes.
  Tell the user it is a one-time install. It ends with a line starting `[setup] READY`; any
  other ending is an error with a fix in the message or in
  [references/troubleshooting.md](references/troubleshooting.md). `lv doctor` shows what is
  installed without changing anything. The other commands also run setup if it is missing.
- **Run the pipeline end to end without asking for confirmation at each step.** Stop only for
  real blockers: notes you cannot open or read, a setup step that needs an administrator
  password, or a request that is ambiguous in a way that changes the video.
- WORK defaults to `./lecture-videos/<name>` (or the user's configured `work_root`). Put the MP4
  where the user asked; otherwise the default in WORK is fine. Keep WORK: the `.tex`, the
  transcript and the audio cache make later edits cheap.

## 1. Read the notes yourself first

`ingest` writes `WORK/source.txt` (pages with a text layer), `WORK/manifest.tsv` (how each page
was read), full-size images of pages that need eyes (`WORK/pages/`), and **glance sheets**
(`WORK/glance-*.jpg`, six pages each).

- **Look at every glance sheet.** They catch margin annotations, highlighted passages and
  figures that text extraction misses, for roughly the token cost of one full page per sheet.
  If a sheet shows handwriting or annotations on a typed page, re-run with `--visual 3,7-9` to
  get those pages at full size.
- **Handwritten or scanned pages** (`[handwritten/scanned]`, `[image]`) must be read at full
  size: open every such image and write `WORK/transcript.md` with the content in order,
  equations in LaTeX, and a one-line description of each figure (axes, labels, key numbers).
  Mark anything illegible as `[illegible]` rather than inventing it. Handwritten notes are often
  the user's own class notes, so treat them as the primary source. If you cannot view images,
  say so and ask for a typed version instead of guessing.
- **Typed pages with figures** (`[has figure]`): open the full-size image only when you need a
  value or label you cannot read on the glance sheet.
- From then on plan only from `source.txt` + `transcript.md`; do not re-read images.
- `.docx`, `.pptx` or `.key` notes: export them to PDF first (for example with LibreOffice
  `soffice --headless --convert-to pdf`), then ingest the PDF.

While reading, note errors or inconsistencies in the notes (typos in numbers, swapped labels).
Use the correct value in the video and list each correction in your final report.

### 1b. Fill gaps from reliable sources
Notes are often terse: a skipped derivation step, a term used before it is defined, a figure
without explanation. When something would confuse a student, and you have web access, search
briefly (2-5 targeted queries, not a literature review) for a clear explanation at the right
level: university course notes and OCW, LibreTexts, standard textbooks, review articles for
graduate-level points. Prefer sources that agree with the notes' notation; when they conflict,
follow the notes and mention the difference. Keep additions short and in service of the notes'
content, pitched for undergraduates first with an optional graduate-level remark, and list the
sources you used in the final report. Don't add topics the lecture doesn't cover.

## 2. Plan before writing (in your head or a few lines)
- **Length**: aim for **about 10 minutes** (9-11) unless the user gives another length. Depth
  beats coverage: if the notes hold more than 10 minutes can explain without skipping steps,
  cover the core thoroughly, then tell the user what was left out and offer a part 2. Budget
  narration at **≈ 155 words per minute of target length, minus 15 s per checkpoint** (the
  default voice speaks ~165 wpm; line pauses use the rest). A 10-minute video ≈ 1,350 words +
  4 checkpoints (measured: 1,481 words + 4 checkpoints = 9.9 min).
- **Arc**: title → motivation → concepts in the notes' order → worked example(s) → summary. One
  idea per frame, 1-5 overlay steps per frame, ~40-70 pages total.
- **Logic chain**: list the chain of reasoning as numbered steps (what is assumed, what follows,
  and why). Every derivation goes from its starting principle to the result with **no skipped
  steps**: each algebra move gets its own line, each assumption is stated where it is used, and
  each new symbol is defined before it appears. If the notes jump ("it can be shown that…"),
  fill the gap (§1b). A student should never have to ask "where did that come from?"
- **Visuals carry the lecture**: plan the picture before the words. Every concept frame needs a
  visual: a diagram, plot, or **physical model** (atoms, a lattice, a tank-and-pipe picture of a
  mass balance, a lever for the lever rule). Show what the symbols stand for physically, not
  just the equations. Redraw every figure as original TikZ/pgfplots (never paste the handout's
  images). Build diagrams step by step with overlays, and use 3-6 short animations where motion
  is the point (a cooling path, a sweeping tie line, a gliding dislocation). Patterns:
  [references/visual-cookbook.md](references/visual-cookbook.md).

### How to explain (this is what makes the video worth watching)
- **Talk like a good tutor, not a textbook.** Everyday wording ("so basically", "here's the
  trick", "think of it like…"), short sentences, and *why* before *what*. Anticipate the
  confusion ("this looks backwards at first, and here's why it isn't").
- **Explain every important equation twice:**
  1. *Mathematically*: where it comes from, step by step, and what each term is.
  2. *Physically / intuitively*: what it means in the real system, with an analogy or a limiting
     case ("if c sits right at c′, the alloy is all liquid, and the formula gives exactly that").
  Put both on screen: the math lines, then a one-line "physically:" note or a picture.
- After each derivation, run a quick sanity check aloud: units, a limiting case, or a number
  from the diagram.
- **Checkpoints**: 3-5 per 10 minutes, placed right after the concept they test (§4).

## 3. Write `WORK/lecture.tex`
`init` already copied [assets/template.tex](assets/template.tex) to `WORK/lecture.tex`; it shows
every construct. Replace its example frames with the lecture. Rules that matter:

- `\usepackage{lecturevideo}` loads the theme (ivory paper, dark ink, one red accent, or the
  user's own branding if configured), the palette (`accent`, `ink`, `mute`, `blu`, `grn`,
  `gold`), figure styles (`pd` axis, `dot`, `lab`, `note`, `tie`, `atom`, `atomA`, `atomB`) and
  the narration commands. Don't restyle the theme inside the lecture.
- **Narration**: `\say<n>{...}`, one per overlay page `n`, placed at the top of the frame.
  `\say<2-13>{...}` narrates an animation span. `\wait<n>{2}` holds a page silently. Every
  page needs one; the renderer names any page that is missing.
- **Spoken text is plain English**: numbers and symbols as words ("forty six percent", "T
  three", "seven hundred seventy nine degrees", "alpha plus beta"). No LaTeX and no `%`, `&`,
  `#`, `$` inside `\say`. Say what to look at ("watch the dot", "notice the tie line"), then why
  it matters. Expand on the slide text rather than reading it out word for word.
- **Slides carry real explanation.** A viewer who pauses, rewinds, or revises from the PDF
  should be able to follow from the slides alone. Next to each visual, put 3-5 bullets of up to
  ~15 words each (key fact, condition, consequence, physical meaning). For derivations, show
  every step as its own line with a short reason beside it ("mass balance on B", "divide by W"),
  revealed as the narration reaches it, ending with a "physically:" line in the accent colour.
  If a derivation needs more than ~6 lines, continue on the next frame (repeat the last line at
  the top) rather than cramming.
- **Layout**: visual on one side (about 55%), text on the other (`columns`), or the visual above
  and 2-3 lines below. Academic and uncluttered: one idea per frame, the accent colour only for
  emphasis, results and state markers.
- Figure macros that take `#1` go in the **preamble** (a `#` in a frame body breaks beamer).
- Any LaTeX package the lecture needs (`siunitx`, `chemfig`, …) may be used; when the private
  TinyTeX is in use, missing packages are installed automatically on first compile.

## 4. Exam-style checkpoints
```latex
\examq[5]{Checkpoint: lever rule}
  {slide question}{spoken question}{slide answer}{spoken answer}
```
This makes 1 question page (narrated, then "You have 5 seconds."), 5 silent one-second
countdown pages with a shrinking ring, and 1 narrated answer page.

Write questions like a real exam on *this* lecture: concrete given numbers, one clear task,
answerable in ~30 s by someone who followed the video, with a short worked answer. Mix types:
- **Calculate**: "An alloy of 35 wt.% B at T₃ with c′ = 20, c″ = 85: what fraction is liquid?"
- **Read the diagram**: "A 20 wt.% Ag alloy is at 900 °C. Which phases, and roughly what compositions?"
- **Predict**: "A 5 wt.% Ag alloy is cooled slowly from 800 °C to 500 °C. What forms, and where?"
- **Identify / classify**: "Liquid → α + β at one temperature: which invariant reaction is this?"
- **Spot the error**: "A student uses c″ − c over the tie line for the solid fraction. What went wrong?"

Avoid vague prompts ("what is a phase?"), trivia not taught in the notes, and multi-part
questions. The answer must show the reasoning step, not just the result. Take the numbers from
the diagram or equation the video just showed, so question, figure and answer agree. Questions
built on a common misconception work well ("halving the pin spacing doubles the source stress:
true or false?"). Keep the 5-second countdown (the slide says "pause if you need longer"); use
`\examq[8]` only if the user asks for longer pauses.

## 5. Check, then render
```bash
lv check WORK/lecture.tex
```
It compiles, prints pages, narrated words, an estimated duration and `layout:` warnings
(content too tall or lines too wide, with source line numbers), and writes numbered contact
sheets `WORK/lecture_build/sheet-*.png`. **Look at the sheets** for collisions, clipped labels,
off-curve markers or empty frames; fix them and re-run (cheap). If you cannot view images, fix
every `layout:` warning and keep figures simple. If the estimate misses the target length by
more than ~10%, trim or extend narration now (not the checkpoints). Then:
```bash
lv render WORK/lecture.tex ["OUT/Lecture title.mp4"]
```
Narrator: Microsoft Edge neural voice `en-GB-SoniaNeural` (free, needs internet) at `+10%`,
720p. Offline or if Edge fails, it falls back automatically to the bundled Kokoro voice
`bf_emma`. Options: `--tts edge|kokoro|say`, `--voice <id or profile>`, `--rate`, `--height`.
When the user names a voice or wants their own (including a cloned voice), read
[references/voices.md](references/voices.md).

**Subtitles come free.** Every render also writes `OUT.srt` and `OUT.vtt` beside the MP4 and
embeds a selectable subtitle track, built from the `\say` text and timed from the synthesized
audio, so they cost no tokens and stay in sync after edits. Never transcribe the video or write
subtitles by hand. They show the narration as written (before `lexicon.tsv` respellings).
`--no-subs` turns them off.

Pronunciation fixes go in `WORK/lexicon.tsv` (`written<TAB>spoken`), applied to audio only.
Re-rendering after an edit takes seconds, because unchanged lines come from the audio cache.

## 6. Report back
Give the video path (and its `.srt`/`.vtt` subtitles), duration, page and checkpoint counts, any corrections to the notes, the
sources used to fill gaps, which figures are schematic redraws, and what was left out (offer a
part 2). Keep WORK for edits.

## Personal settings
Branding (logo, colours, an institution's beamer theme), default voice, work and output
folders live outside the skill, in the user's config folder, so the skill stays portable:
[references/customization.md](references/customization.md). Never edit the skill's own assets
for one user's preferences.

## Why it is built this way
- One source file keeps slides and narration aligned; LaTeX writes the page-accurate narration
  map (`.narr`) itself, so overlays, macros and loops can't desynchronize audio.
- Token cost scales with the narration and diagrams you write, not with video length;
  everything downstream is deterministic and cached by text hash.
- Static pages + a single ffmpeg encode keep a 10-minute render around a minute.
- Every dependency is a pip wheel or a relocatable download in one cache folder, so no
  administrator rights are needed and deleting that folder uninstalls everything.
