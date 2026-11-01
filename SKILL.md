---
name: lecture-notes-to-video
description: Turn lecture notes, slides, chapters or problem sets into narrated study videos (MP4), in English or Chinese, with academic slides, animated demonstrations, actual homework retrieval questions and follow-up recall exercises. Use when asked to make a video, narrated walkthrough, lecture recording or visual study explanation from supplied material.
license: MIT (see LICENSE)
compatibility: "Needs a shell, Python 3.8+ and internet on first run (about 300 MB into a user cache: Python packages, offline voices, ffmpeg, and TinyTeX when no LaTeX is installed; Chinese adds 40 MB of fonts). Elaborated visuals add 3-6 MB of JavaScript libraries and use the installed Chrome or Edge, or fetch a headless Chrome (100-130 MB). Tested on macOS and Linux; Windows is untested. Image viewing is needed for handwritten notes and recommended for checking slides."
metadata:
  version: "2.4.0"
---

# Lecture notes → narrated lecture video

The video has one source file: a beamer `lecture.tex` holding slides, diagrams and narration
together. Also write a short `learning-plan.md`, `recall.md` and separate `recall-answers.md`
in WORK; they track exercise sources and support later practice. The bundled scripts handle
installation and rendering (LaTeX → PNG pages → text-to-speech → ffmpeg → MP4); later edits
re-synthesize only the lines that changed.

## Quick start: the whole pipeline

Every step is one command: `python3 <skill-dir>/scripts/lv.py <command>`, where `<skill-dir>`
is the absolute path of the folder containing this file (on Windows use `py -3` instead of
`python3`). Below, `lv` is shorthand for that whole command; write it out in full each time,
because shell variables usually do not persist between your commands.

```bash
lv setup                           # 0. one-time install; give it a 10-minute timeout or run it in the background
lv init PHYS101-L05                # 1. copies the template into the work folder (WORK); prints `branding:`, then WORK
lv brand --logo F --name "NAME"    #    only if init said `branding: ask` and the user wants branding (see Branding)
lv ingest notes.pdf --out WORK     #    any mix of .pdf .png .jpg .heic .md .txt; several files are fine
#                                       its first line is the notes' language: settle the video's language now (§0)
#                                       ask for homework; ingest it separately into WORK/homework/
#                                       read the notes (§1), plan (§2), write WORK/lecture.tex (§3-4)
lv scene WORK/scenes/NAME.html     #    elaborated only: check each animated scene (see Visual level)
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
  password, or a request that is ambiguous in a way that changes the video. The planned
  questions are the homework exercises and visual level (each lecture), plus branding when
  unset: ask together right after `init`, skipping information already supplied. Keep reading
  the notes while waiting; exercise selection stays pending until homework arrives or the user
  explicitly says none/declines. See the intake rule below.
- WORK defaults to `./lecture-videos/<name>` (or the user's configured `work_root`). Put the MP4
  where the user asked; otherwise the default in WORK is fine. Keep WORK: the `.tex`, the
  transcript and the audio cache make later edits cheap.

## 0. Language: settle it before planning
The video is in the language the user asks for; otherwise in the language of the notes, which
`lv ingest` prints first (`language: en` or `zh`; for handwritten pages, the language you read).
- **English**: follow this file exactly as written. Do not read the Chinese reference and do not
  add the `zh` option; nothing Chinese is loaded and the output is the English pipeline's.
- **Chinese**: run `lv init NAME --lang zh` (it swaps in the Chinese template while
  `lecture.tex` is unedited), then read [references/chinese.md](references/chinese.md) before
  planning. Its rules replace this file's word budget (§2), spoken-text rules (§3), checkpoint
  wording (§4) and default voice (§5); everything else here applies.
- Any other language: the English pipeline with a matching voice ([references/voices.md](references/voices.md)).

## Branding: ask once, then remember
Slides can carry the user's logo and a name (institution, department, course or channel): the
logo with the name beside it on the title page, and the logo small at the left of every frame
title, on the built-in palette and layout. `lv init` prints a `branding:` line; act on it:
- **`branding: ask`**: nothing is decided yet, so ask the user once, in one short message:
  would they like their logo and a name on the slides, and if so, the logo file (PNG, JPG, PDF
  or SVG) and the exact name to show (plus a Chinese name, if they also make Chinese videos).
  Ask straight after `init`; reading the notes can go on while you wait, so the answer never
  holds up the video. Then:
  - logo and/or name: `lv brand --logo FILE --name "NAME"` (`--name-zh "中文名"` for Chinese
    lectures). It tidies the logo (clears a plain white background, trims margins, converts
    SVG), test-builds the slides and prints a preview image: look at it before going on.
  - no: `lv brand --none`. The answer is saved, so the question does not come back.
  - nobody can answer (an automated run with no user to ask): carry on unbranded and save
    nothing, so the question is asked next time.
- **Anything else** (a saved name, `none`, a custom brand file): the user already decided, so
  do not ask. Say in the report which branding the video used and that `lv brand` changes it.
- Branding given in the request ("put our logo ~/logo.png on it") already answers the
  question: run `lv brand` without asking. Only for this lecture: add `--work WORK`.

Use only a logo the user says they may use. `--blackletter` sets a Latin-script name in Gothic
letters (a diploma look); colours and whole themes: [references/customization.md](references/customization.md).

## Homework: ask for each lecture
Before selecting retrieval questions, ask for the corresponding homework/problem set, its
figures, and any available solutions. Bundle this with the visual-level question (and branding
when relevant). If the exercises are already supplied, read them without asking again.
Keep reading the notes while waiting, but do not silently substitute invented questions.
If the user explicitly has none or declines, use clearly labelled author-written problems.
Ingest homework separately into `WORK/homework/`; preserve original problem IDs and difficulty.
Read [references/learning-design.md](references/learning-design.md) before planning for the
attempt, consolidation, recall and spoken-explanation rules.

## Visual level: ask every lecture
The user picks one of two levels for each lecture:
- **Basic** (the default): slides that teach the way Khan Academy and Brilliant do: concrete
  pictures first, one colour per idea, labels and equations hand-written as they are spoken, a
  pointer, camera zooms, parameter sliders, soft fades. No extra downloads; renders as fast as
  plain slides.
- **Elaborated**: Basic plus 2-6 full-screen animated scenes per 10 minutes (2D builds with real
  motion, maths animation with the Manim API, 3D, physics, quantum and materials-science scenes) at 1080p, assembled from
  tested parts: examples, building blocks and manim-web. First use fetches 3-6 MB of libraries
  (and a headless Chrome only if no Chrome or Edge is installed). It costs more of your time and
  tokens and a few more minutes of rendering (README, Time).

Ask in one short line, e.g. "Basic or elaborated visuals? Elaborated adds animated scenes (3D,
simulations) and takes longer to make." If the request already names a level, or clearly asks
for animated 3D scenes or simulations, don't ask. If nobody can answer (an automated run), use
Basic. Then:
- **Basic**: read [references/visual-style.md](references/visual-style.md) before planning (§2).
- **Elaborated**: read it and [references/scenes.md](references/scenes.md) before planning.

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

## 2. Plan the lesson and exercises
- **Length**: aim for about **10 minutes** (9–11) unless the user specifies otherwise.
  Count narration, question reading, worked solutions and embedded reflection/attempt holds.
  Estimate narrated words as `155 × (target minutes − silent hold seconds / 60)`, then use
  the actual check/render estimate. Time spent working with the player paused is additional;
  estimate and report it separately. Preserve reasoning and thinking time; split dense notes
  into another part and report coverage rather than rushing to fit.
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
- **Teach with the picture** ([references/visual-style.md](references/visual-style.md)): the
  concrete thing before the symbol; one colour per idea in picture, text and speech; labels and
  results written on (`\lvwrite`) as the narration says them; a pointer or halo on what "this"
  is; zoom in to work and pull back to conclude (`\lvzoom`); build results term by term;
  "Predict:" before a reveal; sweep a parameter with a slider (`\lvslider`) when the idea is
  "how does it depend on…". Elaborated: decide which 2-6 moments become scenes
  ([references/scenes.md](references/scenes.md)).

### How to explain (this is what makes the video worth watching)
- **Write for a listener.** Use explicit nouns, stable names for quantities, short reasoning
  steps and audible links between them. Explain what changes, why it changes, and how the
  equation expresses that relation. Define terms before using them, point to the corresponding
  visual, and keep essential givens visible. Replace literary phrasing and filler with the
  actual mechanism or mathematical reason. Use the examples and spoken clarity check in
  [references/learning-design.md](references/learning-design.md).

- **Explain every important equation twice:**
  1. *Mathematically*: where it comes from, step by step, and what each term is.
  2. *Physically / intuitively*: what it means in the real system, with an analogy or a limiting
     case ("if c sits right at c′, the alloy is all liquid, and the formula gives exactly that").
  Put both on screen: the math lines, then a one-line "physically:" note or a picture.
- After each derivation, run a quick sanity check aloud: units, a limiting case, or a number
  from the diagram.
- **Settle and connect** after each major derivation or demonstration: hold the completed
  visual still, connect physical meaning → governing principle → conditions of use, and ask
  one specific explanation. Add a silent `\wait<n>{6}` starting hold with that visual still
  present. Budget these moments and the worked homework solutions inside the video length.
- **Homework checkpoints**: begin with roughly 1–2 substantial actual exercises per 10 minutes
  and adjust to their complexity (§4). Small predictions are additional teaching beats.

## 3. Write `WORK/lecture.tex`
`init` already copied [assets/template.tex](assets/template.tex) to `WORK/lecture.tex`; it shows
every construct. Replace its example frames with the lecture. Edit the template `init` gave you
and keep its `\usepackage` line exactly as it is (for Chinese it reads `[zh]`). Rules that matter:

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

## 4. Homework retrieval and later recall
Use actual exercises from the homework requested at intake, preserving their givens,
subparts and reasoning demand. Keep the source file/page and exercise ID in
`WORK/learning-plan.md` and label the question with that ID. Teach the prerequisites, then
ask the learner to attempt the problem before seeing its worked solution. Do not replace
hard homework with a quick invented lookalike.

```latex
\attemptq[15]{Homework: original exercise ID}
  {actual question and required givens}{spoken question}
  {worked solution}{spoken reasoning and check}
```
This makes a narrated question with an explicit pause-and-work instruction, a still question
page held for 15 seconds, and a separate narrated solution frame. The hold is time to pause
the player, not a limit for solving the problem. An MP4 cannot enforce an attempt. Give a
realistic suggested working time; use ordinary frames for long questions or multi-frame
solutions. Keep answers and hints out of the question image and its narration/subtitles.
The old `\examq` countdown remains available for existing lectures; use `\attemptq` for new
homework retrieval. Full selection, feedback and timing rules:
[references/learning-design.md](references/learning-design.md).

Also write `WORK/recall.md` (three prompts: explain, reconstruct, reattempt an actual homework
item) and `WORK/recall-answers.md` (separate hints, answers and video locations). Suggest a
closed-notes attempt the next day and about a week later, adjusting to difficulty. Label any
author-written fallback when the user has explicitly declined or has no homework.

## 5. Check, then render
Before the layout check, verify exercise fidelity and worked answers against their sources,
inspect difficult narration using the spoken clarity check in `references/learning-design.md`,
and confirm that every major derivation/demo has a still consolidation moment. Check that
question pages and their narration contain no premature solutions, and that both recall
files are present with answers separate from prompts.

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
720p (1080p when the lecture has scenes); slide changes dissolve over 0.25 s (`--fade 0` for hard
cuts). Scenes are recorded after the narration, so each beat lasts its sentence. Offline or if Edge fails, it falls back automatically to the bundled Kokoro voice
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
Give the video path (and its `.srt`/`.vtt` subtitles), duration, page and checkpoint counts, the visual level
(and the scenes, if elaborated), the branding used, any corrections to the notes, the
sources used to fill gaps, which figures are schematic redraws, and what was left out (offer a
part 2). Also link `recall.md` and `recall-answers.md`, list the homework exercise IDs (or disclosed
author-written fallback), and distinguish MP4 duration from suggested paused practice time.
Keep WORK for edits.

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
- Scenes are web pages whose every frame depends only on time, recorded frame by frame after
  the narration exists, so they are exact, repeatable and in step with the voice; the
  libraries are single files, so nothing needs Node or a build step.
- Every dependency is a pip wheel or a relocatable download in one cache folder, so no
  administrator rights are needed and deleting that folder uninstalls everything.
