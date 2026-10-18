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
6. Writes `CACHE/env.json`; `lv.py doctor` reads it.

Uninstall: delete the cache folder (and the config folder for personal settings).

## Common failures
| Symptom | Fix |
|---|---|
| `download failed` / certificate errors | Check internet or proxy (`HTTPS_PROXY`). Downloads retry, then fall back to `curl`. Re-run `lv.py setup`. |
| `TinyTeX needs perl` (minimal Linux) | Run the printed command (e.g. `sudo apt-get install -y perl`), then setup again. Setup installs it itself when running as root or with passwordless sudo. |
| System LaTeX builds the template but a lecture needs a missing package (`File 'x.sty' not found`) | Install the package with the system's TeX manager, or run `lv.py setup --tinytex` to switch to a private TinyTeX that installs packages on demand. |
| `LaTeX failed` with a real error | It is in `lecture.tex`: the message shows the line. Common causes: `#` in a frame body (move macros to the preamble), `%`/`&`/`$` inside `\say`, unbalanced braces. |
| `pages without \say or \wait: [...]` | Add a `\say<n>` or `\wait<n>` for each listed overlay page. |
| Edge voice unavailable | Automatic fallback to Kokoro; force with `--tts kokoro`. |
| Broken venv after an OS upgrade | Delete `CACHE/venv` and run setup. |
| `Operation not permitted` reading notes (macOS privacy) | Ask the user to move the file somewhere readable or grant the terminal access to that folder; do not guess the content. |

## Offline use
After one successful setup, everything works offline except the default Edge voice, which
falls back to Kokoro by itself. To pre-install for an offline machine, run setup online once
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
| `HTTPS_PROXY` | proxy for downloads |
