# Troubleshooting

Read this when `lv.py setup` (or the automatic first-run setup) fails, when working offline,
or on Windows.

## What setup does (in order; every step is skipped when already done)
1. **uv**: uses one on PATH, else downloads the standalone binary to `CACHE/bin/`.
2. **Python 3.12 venv** at `CACHE/venv`, with Python itself managed by uv inside `CACHE/python`
   (no system Python is touched), then `pip install -r scripts/requirements.txt` (wheels only).
3. **ffmpeg**: a system ffmpeg with libx264 if present, else the static build from `imageio-ffmpeg`.
4. **LaTeX**: compiles `assets/template.tex` with the system TeX. If there is none, or it lacks
   packages and cannot install them without sudo, downloads TinyTeX (~70 MB) to `CACHE/TinyTeX`
   and installs the needed packages with its `tlmgr`. Nothing is added to PATH.
5. **Kokoro** model files (~115 MB) to `CACHE/kokoro`, verified by loading them.
6. With `--zh` (and on every later setup once installed, where a failure only switches the
   Chinese extras off): Noto Serif/Sans SC to `CACHE/fonts` (~40 MB), a XeLaTeX build of
   `assets/template-zh.tex`, `scripts/requirements-zh.txt` into the venv, and Kokoro v1.1-zh
   (~165 MB) to `CACHE/kokoro-zh`, tested with one Chinese sentence. Without `--zh`, the first
   Chinese lecture fetches only the fonts and runs the XeLaTeX test.
7. Writes `CACHE/env.json`; `lv.py doctor` reads it.

Uninstall: delete the cache folder (and the config folder for personal settings).

## Common failures
| Symptom | Fix |
|---|---|
| `download failed` / certificate errors | Check internet or proxy (`HTTPS_PROXY`). Downloads retry, then fall back to `curl`. Re-run `lv.py setup`. |
| `TinyTeX needs perl` (minimal Linux) | Run the printed command (e.g. `sudo apt-get install -y perl`), then setup again. Setup installs it itself when running as root or with passwordless sudo. |
| System LaTeX builds the template but a lecture needs a missing package (`File 'x.sty' not found`) | Install the package with the system's TeX manager, or run `lv.py setup --tinytex` to switch to a private TinyTeX that installs packages on demand. |
| `LaTeX failed` with a real error | It is in `lecture.tex`: the message shows the line. Common causes: `#` in a frame body (move macros to the preamble), `%`/`&`/`$` inside `\say`, unbalanced braces. |
| `pages without \say or \wait: [...]` | Add a `\say<n>` or `\wait<n>` for each listed overlay page. |
| Edge voice unavailable, or a render stalls after `tts: N lines, M new` | Automatic fallback to Kokoro: a line with no reply within 30 s (plus 0.1 s per character) is retried twice, then the offline voice takes over. Force it with `--tts kokoro`. |
| Broken venv after an OS upgrade | Delete `CACHE/venv` and run setup. |
| `Operation not permitted` reading notes (macOS privacy) | Ask the user to move the file somewhere readable or grant the terminal access to that folder; do not guess the content. |
| `contains Chinese text but is set up as English` / `set up as Chinese ([zh]) but its narration has no Chinese` | The lecture's language and its text disagree: see [chinese.md §1](chinese.md#1-setup-one-option-switches-everything). |
| `This LaTeX builds English lectures but not Chinese ones` (at `init --lang zh`) | Follow the message: install XeLaTeX + ctex with the system's TeX manager, or `lv.py setup --tinytex` to move every lecture to a private TinyTeX. |
| `Chinese fonts not downloaded; using this system's default Chinese fonts` | Offline at the first Chinese lecture. Slides use ctex's default fonts if the system has them; run `check` again online to get the Noto fonts. |
| `edge-tts failed ... Chinese narration needs internet` | Connect, or install the offline Chinese voice once: `lv.py setup --zh`. |
| `... was not written by lv.py brand (or was edited since), so it is left alone` | The brand file is hand-written or hand-edited. Edit it directly, or rename it and run `lv.py brand` again. |
| `cannot convert an SVG logo here` / `cannot read ... as SVG` | Save the logo as PNG (transparent if possible) or PDF and run `lv.py brand` again. |
| `scene NAME.html: the scene did not start` / `script errors while playing` | The message gives the JavaScript error and its line: [scenes.md §6](scenes.md#6-problems). |
| `scenes/NAME.html has N beats ... but the lecture says \lvscene{NAME}{M}` | Make the number of `LV.beat` calls, the `\lvscene` count and the `\say<k>` lines agree. |
| `the browser ... did not start` (elaborated lectures, Linux) | Headless Chrome needs a few system libraries (`sudo apt-get install -y libnss3 libatk-bridge2.0-0 libgbm1 libxkbcommon0 libasound2t64`), or install Chromium, or point `LV_CHROME` at a browser. |
| `scenes: could not fetch a verified copy of ...` / `the manim-web download did not match its checksum` | The scene libraries need internet once: connect and run `lv.py scene --install`. |
| `the slides do not build with this logo or name, so nothing was changed` | The message shows the LaTeX error: usually a damaged image file, or a name in a script the English slides cannot typeset (put Chinese names in `--name-zh`). |

## Offline use
After one successful setup, everything works offline except the default Edge voice, which
falls back to Kokoro by itself, and the first elaborated lecture, which fetches ~3 MB of scene
libraries (and a headless Chrome when none is installed). Chinese lectures fall back to the offline Chinese voice, which
needs `lv.py setup --zh` once while online. To pre-install for an offline machine, run setup online once
and copy the cache folder (same OS and CPU type).

## Windows (untested)
Run commands with `py -3 scripts\lv.py ...` (or `python`). Setup downloads the Windows uv and
`TinyTeX-1-windows.exe` (a self-extracting archive). If a step fails, a system LaTeX
(MiKTeX or TeX Live with latexmk and perl on PATH) and `ffmpeg` on PATH also work. Report
problems with the full error text.

## Environment variables
| Variable | Meaning |
|---|---|
| `LECTURE_VIDEO_CACHE` | cache folder (venv, TinyTeX, models, audio cache) |
| `LECTURE_VIDEO_CONFIG` | config folder (personal settings) |
| `LV_CHROME` | browser used to record animated scenes (default: installed Chrome, Edge, Chromium or Brave, else a fetched headless Chrome) |
| `HTTPS_PROXY` | proxy for downloads |
