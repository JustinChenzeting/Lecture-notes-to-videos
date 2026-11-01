"""Shared helpers for lecture-notes-to-video. Standard library only.

Imported by lv.py (any system Python 3.8+) and by render_lecture.py (the skill's venv):
platform paths, the user config, the record written by `lv.py setup`, and LaTeX
compilation that installs missing TeX packages on the fly when the TeX tree is writable.

Locations (override with environment variables):
  LECTURE_VIDEO_CACHE   downloads and envs: venv, TinyTeX, Kokoro models, Chinese fonts, TTS cache
                        default ~/.cache/lecture-video  (%LOCALAPPDATA%\\lecture-video on Windows)
  LECTURE_VIDEO_CONFIG  personal settings: config.json, voices/<name>/, tex/ (branding)
                        default ~/.config/lecture-video (%APPDATA%\\lecture-video on Windows)
"""
import hashlib, json, os, re, shutil, subprocess, sys
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
    """Optional CONFIG/config.json: work_root, output_dir, voice, tts, rate, height, branding."""
    f = CONFIG / "config.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError as e:
        sys.exit(f"{f} is not valid JSON: {e}")


def save_config(cfg: dict):
    CONFIG.mkdir(parents=True, exist_ok=True)
    (CONFIG / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ------------------------------------------------------------------- branding
# A lecturevideo-brand.sty in the work folder (that lecture) or in CONFIG/tex (every lecture)
# replaces the built-in theme. `lv.py brand` writes one with a record beside it, so it can tell
# its own files from a hand-written theme, which it never overwrites.
BRAND_STY, BRAND_JSON = "lecturevideo-brand.sty", "lecturevideo-brand.json"


def brand_record(d: Path):
    """The record of a brand file written by `lv.py brand` and unchanged since, else None."""
    try:
        rec = json.loads((d / BRAND_JSON).read_text(encoding="utf-8"))
        sty = (d / BRAND_STY).read_bytes()
    except (OSError, ValueError):
        return None
    return rec if rec.get("sha1") == hashlib.sha1(sty).hexdigest() else None


def brand_status(work=None) -> str:
    """What the next lecture is branded with; 'ask' while nothing has been decided."""
    for d, scope in ((Path(work) if work else None, "this lecture only"), (CONFIG / "tex", "saved")):
        if d and (d / BRAND_STY).exists():
            rec = brand_record(d)
            if rec is None:
                return f"custom brand file {d / BRAND_STY}"
            if rec.get("none"):
                return f"none ({scope}; change with lv.py brand)"
            what = " + ".join(x for x in (rec.get("name") or rec.get("name_zh"), rec.get("logo") and "logo") if x)
            return f"{what} ({scope}; change with lv.py brand)"
    if load_config().get("branding") == "none":
        return "none (the user chose no branding; change with lv.py brand)"
    return "ask"


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


# ------------------------------------------------------------------- language
# A lecture is English unless its preamble says \usepackage[zh]{lecturevideo}. That one switch
# selects XeLaTeX + ctex, the Chinese voice, subtitles and length estimate; English lectures
# take exactly the code paths they always took.
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")  # Chinese characters
FONTS = CACHE / "fonts"  # Noto Serif/Sans SC, fetched by lv.py for the first Chinese lecture
ZH_FONTS = ["NotoSansSC-Regular.otf", "NotoSansSC-Bold.otf", "NotoSerifSC-Regular.otf", "NotoSerifSC-Bold.otf"]


def tex_source(tex: Path) -> str:
    """The .tex without % comments: a % after an even run of backslashes (none, or \\\\ for a
    line break) starts one; \\% is a percent sign."""
    return re.sub(r"(?<!\\)((?:\\\\)*)%[^\n]*", r"\1", tex.read_text(encoding="utf-8", errors="replace"))


def lecture_lang(tex: Path) -> str:
    """'zh' if the lecture loads lecturevideo with the zh option, else 'en'."""
    m = re.search(r"\\usepackage\s*\[([^\]]*)\]\s*\{lecturevideo\}", tex_source(tex))
    return "zh" if m and "zh" in (o.strip() for o in m.group(1).split(",")) else "en"


# ------------------------------------------------------------------ TeX packages
_MISSING = [
    (re.compile(r"[Ff]ile `([^']+)' not found"), ""),  # LaTeX, package and encoding errors
    (re.compile(r"! I can't find file `([^']+)'"), ""),
    (re.compile(r"pdfTeX error: \S+ \(file ([^)\s]+)\): cannot open"), ""),  # .enc, .pfb, .map
    (re.compile(r"! Font [^=]+=(\S+?)(?: at \S+)? not loadable: Metric \(TFM\) file"), ".tfm"),
    (re.compile(r'The font "([^"/]+)" cannot be found'), ".otf"),  # XeLaTeX: e.g. ctex's Fandol fonts
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


def compile_latex(tex: Path, extra_args=(), env=None, extra_inputs=(), brand=True, tries=12, engine="pdf"):
    """latexmk -pdf (engine="xelatex" for Chinese); on 'File not found' errors, install the
    owning TeX packages and retry.

    Returns (ok, log_text)."""
    env = env if env is not None else load_env()
    texbin = env.get("texbin", "")
    e = tool_env(env)
    e["TEXINPUTS"] = texinputs(extra_inputs, brand)
    if engine == "xelatex":  # fontspec finds the cached Noto fonts by file name; "" keeps TeX's own dirs
        e["OPENTYPEFONTS"] = os.pathsep.join([str(FONTS), ""])
    args, installed = list(extra_args), []
    log = tex.parent / f"{tex.stem}.log"
    for _ in range(tries):
        r = subprocess.run(["latexmk", f"-{engine}", *args, "-interaction=nonstopmode", "-halt-on-error", tex.name],
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
