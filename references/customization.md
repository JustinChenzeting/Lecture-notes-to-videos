# Personal settings

Read this when the user wants their own logo, colours, institution theme, default voice, or
default folders. Personal settings live in the user's **config folder**, never in the skill,
so the skill can be shared and updated without carrying anyone's branding or voices.

| | Default location | Override |
|---|---|---|
| Config folder (`CONFIG`) | `~/.config/lecture-video` (Windows `%APPDATA%\lecture-video`) | `LECTURE_VIDEO_CONFIG` |
| Cache folder | `~/.cache/lecture-video` (Windows `%LOCALAPPDATA%\lecture-video`) | `LECTURE_VIDEO_CACHE` |

`python3 <skill-dir>/scripts/lv.py doctor` prints both, plus what it found in them.

```
CONFIG/
├── config.json                 optional defaults (below)
├── lexicon.tsv                 optional pronunciation fixes for every lecture
├── voices/<name>/voice.json    personal voice profiles (references/voices.md)
├── tex/lecturevideo-brand.sty  optional branding, usually written by `lv.py brand`
├── tex/lecturevideo-logo.png   (or .pdf) the logo it uses, and lecturevideo-brand.json, its record
└── brand-preview.png           the last preview `lv.py brand` made
```

## config.json
All keys are optional; command-line flags win.
```json
{
  "work_root": "~/Documents/Lecture Videos",
  "output_dir": "~/Desktop",
  "voice": "isabella",
  "tts": "edge",
  "rate": "+10%",
  "height": 1080,
  "fade": 0.25,
  "zh": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%"},
  "branding": "none"
}
```
`work_root` is where `lv.py init NAME` creates work folders (default `./lecture-videos`).
`output_dir` is where `render` writes the MP4 when no output path is given (default: WORK).
`voice`, `tts` and `rate` are for English lectures; Chinese lectures read the same keys from
`zh` instead (default `zh-CN-YunxiNeural` at `+0%`, see [chinese.md](chinese.md#6-voice)).
`"branding": "none"` records that the user wants no logo or name (`lv.py brand --none` writes it).
`height` sets the video height for every lecture (default 720, or 1080 for lectures with animated
scenes); `fade` the dissolve between slides in seconds (default 0.25, 0 for hard cuts). The visual
level (Basic or Elaborated) is asked for each lecture and has no setting.

## Branding: logo and name (`lv.py brand`)
The agent asks once (SKILL.md, Branding) and runs one command. The result keeps the built-in
palette and layout and adds the logo with the name beside it on the title page, and the logo
small at the left of every frame title.

| Command | Effect |
|---|---|
| `lv.py brand --logo FILE --name "NAME"` | every lecture: writes `CONFIG/tex/lecturevideo-brand.sty` and the logo beside it |
| `--name-zh "中文名"` | the name Chinese lectures show (default: `--name`; a Chinese-only `--name` is used for Chinese lectures only, because English slides cannot show Chinese characters) |
| `--blackletter` | the name in Gothic letters (a diploma look; Latin script only) |
| `--keep-background` | keep a raster logo's plain white background (cleared by default) |
| `--work WORK` | this lecture only: the files go into the work folder, which wins over the saved branding |
| `lv.py brand --none` | no logo or name; saved, so the agent stops asking (`--work WORK --none`: unbranded for this lecture only) |
| `lv.py brand` | show what the next lecture gets |

Logos: PNG, JPG, PDF or SVG (SVG is converted to PDF with `rsvg-convert`, `inkscape` or, failing
both, svglib, which it installs into the skill's Python once, ~10 MB). Raster logos are capped at
1200 px, a plain white background touching the border becomes transparent, and empty margins are
trimmed. Each run test-builds the template (and the Chinese one, once Chinese lectures have been
made here or with `--name-zh`), changes nothing if that fails, and saves a preview of the title
page and one slide. A brand file the command did not write, or that was edited by hand, is never
overwritten or removed.

## Branding by hand: `lecturevideo-brand.sty`
If a file with this name is in the work folder or in `CONFIG/tex/`, `lecturevideo.sty` loads
it **instead of** the built-in theme, after defining the palette, `\lvlogo` and `\lvname`. The
work-folder copy wins, which allows per-course branding.

Minimal brand (built-in look plus a logo, a name and a different accent):
```latex
\ProvidesPackage{lecturevideo-brand}
\usetheme{lecturevideo}              % keep the built-in look
\definecolor{accent}{HTML}{00356B}   % e.g. a university blue
\lvlogo{logo.pdf}                    % file next to this .sty, or an absolute path
\lvname{University of Example}       % beside the logo on the title page
\institute{Department of Physics}
```

An institution's own beamer theme, kept in another folder:
```latex
\ProvidesPackage{lecturevideo-brand}
\makeatletter
\def\input@path{{/path/to/kit/themes/}{/path/to/kit/}}   % where its .sty files and images live
\makeatother
\usetheme{myuniversity}
\colorlet{accent}{univred}           % map the palette onto the kit's colours
\lvlogo{logos/seal.pdf}
```
Keep the palette names (`ink`, `accent`, `mute`, `blu`, `grn`, `gold`, `paper`, `lvlight`,
`lvrule`) defined, because figures and checkpoints use them. Use only logos the user is
entitled to use. `lv.py setup` test-compiles the brand file and warns if it breaks.

## Paths of the bundled pieces
- `assets/lecturevideo.sty`: narration (`\say`, `\wait`), animation (`\lvanim`), checkpoints
  (`\examq`), palette, logo hooks. Shared by every theme.
- `assets/beamerthemelecturevideo.sty`: the built-in theme (moloch-based, falls back to
  metropolis or default beamer on older TeX installs).
- `assets/template.tex`: the starting point copied by `lv.py init`.
- `assets/lecturevideo-zh.sty`, `assets/template-zh.tex`: Chinese lectures (`[zh]` option,
  `lv.py init --lang zh`). A brand file works for both languages; `setup --zh` test-compiles it
  with XeLaTeX too.
- `assets/lexicon.tsv`: shared pronunciation fixes.
