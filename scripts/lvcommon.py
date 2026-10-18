"""Shared helpers for lecture-notes-to-video. Standard library only.

Imported by lv.py (any system Python 3.8+) and by render_lecture.py (the skill's venv):
platform paths, the user config, the record written by `lv.py setup`, and LaTeX
compilation that installs missing TeX packages on the fly when the TeX tree is writable.

Locations (override with environment variables):
  LECTURE_VIDEO_CACHE   downloads and envs: venv, TinyTeX, Kokoro model, TTS cache
                        default ~/.cache/lecture-video  (%LOCALAPPDATA%\\lecture-video on Windows)
  LECTURE_VIDEO_CONFIG  personal settings: config.json, voices/<name>/, tex/ (branding)
                        default ~/.config/lecture-video (%APPDATA%\\lecture-video on Windows)
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
WINDOWS = os.name == "nt"
ENV_VERSION = 2  # bump when setup's requirements change, so old installs re-run setup


def _base(var, win_var, posix_default):
    if WINDOWS:
        return Path(os.environ.get(win_var) or Path.home() / "AppData" / ("Local" if win_var == "LOCALAPPDATA" else "Roaming"))
    return Path(os.environ.get(var) or Path.home() / posix_default)


CACHE = Path(os.environ.get("LECTURE_VIDEO_CACHE") or _base("XDG_CACHE_HOME", "LOCALAPPDATA", ".cache") / "lecture-video").expanduser()
CONFIG = Path(os.environ.get("LECTURE_VIDEO_CONFIG") or _base("XDG_CONFIG_HOME", "APPDATA", ".config") / "lecture-video").expanduser()
ENV_FILE = CACHE / "env.json"


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if WINDOWS else "bin/python")


def load_env() -> dict:
    try:
        return json.loads(ENV_FILE.read_text())
    except (OSError, ValueError):
        return {}


def load_config() -> dict:
    """Optional CONFIG/config.json: work_root, output_dir, voice, tts, rate, height."""
    f = CONFIG / "config.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError as e:
        sys.exit(f"{f} is not valid JSON: {e}")


def ffmpeg() -> str:
    return os.environ.get("LV_FFMPEG") or load_env().get("ffmpeg") or "ffmpeg"


def tool_env(env=None) -> dict:
    """os.environ with the private TeX bin dir (if setup installed TinyTeX) first on PATH."""
    env = env if env is not None else load_env()
    e = dict(os.environ)
    if env.get("texbin"):
        e["PATH"] = env["texbin"] + os.pathsep + e.get("PATH", "")
    if env.get("ffmpeg"):
        e["LV_FFMPEG"] = env["ffmpeg"]
    return e


def texinputs(extra=(), brand=True):
    """Work dir first, then personal branding, then the skill's styles, then TeX's defaults."""
    own = [str(CONFIG / "tex")] if brand else []
    return os.pathsep.join([".", *map(str, extra), *own, str(SKILL / "assets"), ""])


# ------------------------------------------------------------------ TeX packages
_MISSING = [
    (re.compile(r"[Ff]ile `([^']+)' not found"), ""),  # LaTeX, package and encoding errors
    (re.compile(r"! I can't find file `([^']+)'"), ""),
    (re.compile(r"pdfTeX error: \S+ \(file ([^)\s]+)\): cannot open"), ""),  # .enc, .pfb, .map
    (re.compile(r"! Font [^=]+=(\S+?)(?: at \S+)? not loadable: Metric \(TFM\) file"), ".tfm"),
]


_IMAGES = {".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"}  # user files, not TeX packages


def missing_tex_files(log: str):
    """File names a failed LaTeX run could not find (foo.sty, foo.cls, font.tfm, ...)."""
    out = []
    for rx, ext in _MISSING:
        for m in rx.finditer(log):
            name = m.group(1).strip()
            if ext and not name.endswith(ext):
                name += ext
            elif "." not in Path(name).name:
                name += ".tex"  # \input{foo}
            if name not in out and Path(name).suffix.lower() not in _IMAGES:
                out.append(name)
    return out


def tlmgr_path(texbin=""):
    exe = "tlmgr.bat" if WINDOWS else "tlmgr"
    if texbin:
        p = Path(texbin) / exe
        return str(p) if p.exists() else None
    return shutil.which("tlmgr")


def tex_writable(texbin="") -> bool:
    """Packages can be installed without sudo: our TinyTeX, or a user-owned TeX tree."""
    if texbin:
        return True
    kp = shutil.which("kpsewhich")
    if not kp or not tlmgr_path():
        return False
    root = subprocess.run([kp, "-var-value", "TEXMFROOT"], capture_output=True, text=True).stdout.strip()
    return bool(root) and os.access(root, os.W_OK)


def tlmgr_install(pkgs, texbin="", quiet=True) -> bool:
    tl = tlmgr_path(texbin)
    if not tl or not pkgs:
        return False
    r = subprocess.run([tl, "install", *pkgs], capture_output=quiet, text=True, env=tool_env({"texbin": texbin}))
    return r.returncode == 0


def packages_for(files, texbin=""):
    """Map missing file names to TeX Live package names with `tlmgr search --global --file`."""
    tl, pkgs = tlmgr_path(texbin), []
    for name in files:
        r = subprocess.run([tl, "search", "--global", "--file", "/" + name], capture_output=True, text=True,
                           env=tool_env({"texbin": texbin}))
        pkg = None
        for line in r.stdout.splitlines():
            if line and not line[0].isspace() and line.rstrip().endswith(":") and not line.startswith("tlmgr"):
                pkg = line.rstrip()[:-1]
            elif pkg and line.strip().endswith("/" + name):
                pkgs.append(pkg)
                break
    return list(dict.fromkeys(pkgs))


def compile_latex(tex: Path, extra_args=(), env=None, extra_inputs=(), brand=True, tries=12):
    """latexmk -pdf; on 'File not found' errors, install the owning TeX packages and retry.

    Returns (ok, log_text)."""
    env = env if env is not None else load_env()
    texbin = env.get("texbin", "")
    e = tool_env(env)
    e["TEXINPUTS"] = texinputs(extra_inputs, brand)
    args, installed = list(extra_args), []
    log = tex.parent / f"{tex.stem}.log"
    for _ in range(tries):
        r = subprocess.run(["latexmk", "-pdf", *args, "-interaction=nonstopmode", "-halt-on-error", tex.name],
                           cwd=tex.parent, env=e, capture_output=True, text=True)
        text = log.read_text(errors="replace") if log.exists() else r.stdout + r.stderr
        if r.returncode == 0:
            return True, text
        files = [f for f in missing_tex_files(text) if f not in installed]
        if not files or not tex_writable(texbin):
            return False, text or r.stdout + r.stderr
        pkgs = packages_for(files, texbin)
        installed += files
        if not pkgs:
            return False, text
        print(f"TeX: installing {', '.join(pkgs)} for {', '.join(files)}", flush=True)
        if not tlmgr_install(pkgs, texbin):
            return False, text
        args = [a for a in args if a != "-g"] + ["-g"]  # force a full rerun after the failure
    return False, text


def latex_errors(log: str, n=15):
    lines = log.splitlines()
    out = []
    for i, l in enumerate(lines):
        if l.startswith("!"):
            out += lines[i:i + 3]
        elif re.match(r".*\.tex:\d+:", l):
            out.append(l)
    return "\n".join(out[:n]) or "\n".join(lines[-n:])
