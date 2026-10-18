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
└── tex/lecturevideo-brand.sty  optional branding; replaces the built-in theme
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
  "height": 1080
}
```
`work_root` is where `lv.py init NAME` creates work folders (default `./lecture-videos`).
`output_dir` is where `render` writes the MP4 when no output path is given (default: WORK).

## Branding: `lecturevideo-brand.sty`
If a file with this name is in the work folder or in `CONFIG/tex/`, `lecturevideo.sty` loads
it **instead of** the built-in theme, after defining the palette and `\lvlogo`. The work-folder
copy wins, which allows per-course branding.

Minimal brand (built-in look plus a logo and a different accent):
```latex
\ProvidesPackage{lecturevideo-brand}
\usetheme{lecturevideo}              % keep the built-in look
\definecolor{accent}{HTML}{00356B}   % e.g. a university blue
\lvlogo{logo.pdf}                    % file next to this .sty, or an absolute path
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
- `assets/lexicon.tsv`: shared pronunciation fixes.
