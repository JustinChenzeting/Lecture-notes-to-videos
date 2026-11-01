#!/usr/bin/env python3
"""lecture-notes-to-video: one entry point for every step. Standard library only (Python 3.8+).

  python3 lv.py setup [--clone] [--tinytex] [--zh]   install or repair everything (idempotent)
  python3 lv.py doctor                        report what is installed; changes nothing
  python3 lv.py init NAME|DIR [--lang zh]     new work folder holding lecture.tex (from the template;
                                              --lang zh: the Chinese template, swapped in if unedited)
  python3 lv.py brand --logo FILE --name NAME  put a logo and a name on the slides (saved for every lecture)
                                              [--name-zh NAME] [--blackletter] [--work DIR] | --none | (show)
  python3 lv.py ingest NOTES... --out DIR     prepare notes for reading, report their language  [--visual 3,7-9]
  python3 lv.py check DIR/lecture.tex         compile + contact sheets + layout warnings, no audio
  python3 lv.py scene DIR/scenes/NAME.html    check an animated scene (elaborated lectures): beats, errors,
                                              stills, contact sheet  [--install: fetch its libraries]
  python3 lv.py render DIR/lecture.tex [OUT.mp4] [--voice NAME] [--tts edge|kokoro|say|chatterbox]
                                              [--rate +10%] [--height 720] [--no-subs]
                                              (also writes OUT.srt + OUT.vtt and a subtitle track)

init, ingest, check and render run setup automatically the first time, so a new machine
needs no separate install step. Setup downloads (once, into LECTURE_VIDEO_CACHE):
  uv + Python 3.12 venv (edge-tts, kokoro-onnx, pypdfium2, Pillow, imageio-ffmpeg)   ~150 MB
  Kokoro British voices for offline narration                                         ~115 MB
  TinyTeX, only when no working LaTeX is installed                                    ~250 MB
  --clone: a voice-cloning env (Chatterbox; MLX on Apple silicon, PyTorch elsewhere)   ~2-4 GB
  --zh: Chinese fonts + the offline Chinese voice (Kokoro v1.1-zh) + an XeLaTeX test  ~300 MB
--tinytex forces a private TinyTeX even when a system LaTeX exists.
Chinese lectures need no --zh: init --lang zh (or the first check) fetches the fonts (~40 MB) and
tests XeLaTeX; --zh adds the offline Chinese voice, used when Edge is unreachable or with --tts kokoro.
Elaborated lectures (animated scenes) fetch ~3 MB of JavaScript libraries on first use and use the
installed Chrome/Edge/Chromium, or fetch Google's headless Chrome (~100-130 MB) when there is none.
"""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvcommon import (CACHE, CONFIG, ENV_FILE, ENV_VERSION, FONTS, SKILL, WINDOWS, ZH_FONTS,  # noqa: E402
                      brand_status, compile_latex, latex_errors, lecture_lang, load_config, load_env, tlmgr_install,
                      tool_env, venv_python)

SCRIPTS = SKILL / "scripts"
PY_VERSION = "3.12"
UV_URL = "https://github.com/astral-sh/uv/releases/latest/download/"
TINYTEX_URL = "https://github.com/rstudio/tinytex-releases/releases/download/daily/"
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ["kokoro-v1.0.int8.onnx", "voices-v1.0.bin"]
# Installed into a private TinyTeX up front; anything else a lecture uses is fetched on demand.
TEX_PKGS = ["latexmk", "beamer", "pgf", "pgfplots", "moloch", "booktabs", "amsfonts", "newpx", "kastrup",
            "sourcesans", "sourcecodepro", "ly1", "fontaxes", "mweights", "xstring", "xpatch", "pgfopts",
            "carlisle", "translator", "fp", "newtx", "tex-gyre", "oberdiek"]
IMPORTS = "import edge_tts, kokoro_onnx, soundfile, numpy, pypdfium2, PIL, pillow_heif, imageio_ffmpeg"
# Chinese (setup --zh, or fonts on demand). Pinned to release tags, so the files never change.
NOTO_URL = "https://github.com/notofonts/noto-cjk/raw/"
NOTO_PATHS = {f"Noto{k}SC-{w}.otf": f"{tag}/{k}/SubsetOTF/SC/" for k, tag in (("Sans", "Sans2.004"), ("Serif", "Serif2.003"))
              for w in ("Regular", "Bold")}
KOKORO_ZH_FILES = {  # file names must match render_lecture.KOKORO_ZH
    "kokoro-v1.1-zh.int8.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/",
    "voices-v1.1-zh.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/",
    "config.json": "https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/resolve/main/"}
ZH_IMPORTS = "import misaki.zh, misaki.espeak, jieba, pypinyin, cn2an"


def log(msg):
    print(f"[setup] {msg}", flush=True)


def ok(py, code="pass"):
    return Path(py).exists() and subprocess.run([str(py), "-c", code], capture_output=True).returncode == 0


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"command failed: {' '.join(map(str, cmd))}\n{(r.stderr or r.stdout)[-2000:]}")
    return r.stdout


def arch():
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "aarch64"
    if m in ("x86_64", "amd64"):
        return "x86_64"
    sys.exit(f"unsupported CPU architecture: {platform.machine()}")


def musl():
    return platform.system() == "Linux" and platform.libc_ver()[0] != "glibc"


def download(url, dst: Path):
    """urllib with retries; falls back to curl (handles proxies and missing CA bundles)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    log(f"downloading {url.rsplit('/', 1)[-1]}")
    err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(part, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            os.replace(part, dst)
            return dst
        except Exception as e:  # noqa: BLE001 - any failure: retry, then curl
            err = e
            if "CERTIFICATE" in str(e):
                break
            time.sleep(2 * (attempt + 1))
    curl = shutil.which("curl")
    if curl and subprocess.run([curl, "-fsSL", "--retry", "3", "-o", str(part), url]).returncode == 0:
        os.replace(part, dst)
        return dst
    sys.exit(f"download failed: {url}\n  {err}\n  Check the internet connection or proxy, then re-run setup.")


def system_install(pkg):
    """Install a system package when that needs no password (root, or passwordless sudo)."""
    mgrs = {"apt-get": "apt-get update -qq && apt-get install -y -qq {p}", "dnf": "dnf install -y {p}",
            "yum": "yum install -y {p}", "apk": "apk add {p}", "pacman": "pacman -S --noconfirm {p}",
            "zypper": "zypper -n install {p}", "brew": "brew install {p}"}
    mgr = next((m for m in mgrs if shutil.which(m)), None)
    if not mgr:
        return False, f"install '{pkg}' with your system package manager"
    cmd = mgrs[mgr].format(p=pkg)
    if mgr != "brew" and hasattr(os, "geteuid") and os.geteuid() != 0:
        if not shutil.which("sudo") or subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode:
            return False, "sudo sh -c '" + cmd + "'"
        cmd = "sudo -n sh -c '" + cmd + "'"
    log(f"installing system package: {pkg}")
    return subprocess.run(cmd, shell=True).returncode == 0, cmd


# --------------------------------------------------------------------- python
def uv_env():
    e = dict(os.environ)
    e.update(UV_PYTHON_INSTALL_DIR=str(CACHE / "python"), UV_CACHE_DIR=str(CACHE / "uv-cache"),
             UV_PYTHON_PREFERENCE="only-managed")  # the venv must not depend on a system Python
    return e


def ensure_uv():
    exe = "uv.exe" if WINDOWS else "uv"
    for c in (shutil.which("uv"), Path.home() / ".local/bin" / exe, Path.home() / ".cargo/bin" / exe, CACHE / "bin" / exe):
        if c and Path(c).exists():
            return str(c)
    sysname = platform.system()
    target = {"Darwin": "apple-darwin", "Linux": "unknown-linux-" + ("musl" if musl() else "gnu"),
              "Windows": "pc-windows-msvc"}.get(sysname) or sys.exit(f"unsupported OS: {sysname}")
    ext = ".zip" if WINDOWS else ".tar.gz"
    arc = download(f"{UV_URL}uv-{arch()}-{target}{ext}", CACHE / "downloads" / f"uv{ext}")
    tmp = CACHE / "downloads" / "uv-unpack"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.unpack_archive(str(arc), str(tmp))
    src = next(tmp.rglob(exe))
    (CACHE / "bin").mkdir(parents=True, exist_ok=True)
    dst = CACHE / "bin" / exe
    shutil.move(str(src), str(dst))
    dst.chmod(0o755)
    shutil.rmtree(tmp, ignore_errors=True)
    arc.unlink()
    return str(dst)


def ensure_venv(uv):
    venv = CACHE / "venv"
    py = venv_python(venv)
    if ok(py, IMPORTS):
        return py
    if not ok(py):
        shutil.rmtree(venv, ignore_errors=True)
        log(f"creating the Python {PY_VERSION} environment")
        run([uv, "venv", "-q", "--python", PY_VERSION, venv], env=uv_env())
    log("installing Python packages")
    run([uv, "pip", "install", "-q", "--python", py, "-r", SCRIPTS / "requirements.txt"], env=uv_env())
    if not ok(py, IMPORTS):
        sys.exit(f"Python packages did not import in {py}; delete {venv} and re-run setup")
    shutil.rmtree(CACHE / "uv-cache", ignore_errors=True)  # wheels are installed; ~250 MB back
    return py


def ensure_ffmpeg(py):
    ff = shutil.which("ffmpeg")
    if ff and "libx264" in subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout:
        return ff
    return run([py, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"]).strip()


# ------------------------------------------------------------------------ TeX
def assets_hash(zh=False):
    """Stamp of the files a TeX test compiles: English and Chinese are stamped separately, so a
    change to the Chinese files never re-runs (or blocks) English setup."""
    h = hashlib.sha1()
    for f in ("lecturevideo.sty", "beamerthemelecturevideo.sty") + \
            (("lecturevideo-zh.sty", "template-zh.tex") if zh else ("template.tex",)):
        h.update((SKILL / "assets" / f).read_bytes())
    return h.hexdigest()[:12]


def tinytex_bin(root: Path):
    return str(next(p for p in sorted((root / "bin").iterdir()) if p.is_dir()))


def smoke_test(texbin, brand=False, zh=False):
    """Compile the template in a scratch folder: the real test of a TeX install."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tex = Path(d) / "lecture.tex"
        shutil.copy(SKILL / ("assets/template-zh.tex" if zh else "assets/template.tex"), tex)
        good, logtext = compile_latex(tex, env={"texbin": texbin}, brand=brand, engine="xelatex" if zh else "pdf")
        if good and (Path(d) / "lecture.narr").exists():
            return True, ""
        return False, latex_errors(logtext)


def tinytex_prereqs():
    """tlmgr is perl and downloads packages with curl or wget; minimal Linux images may lack both."""
    need = [] if WINDOWS else \
        (["perl"] if subprocess.run(["perl", "-MFile::Find", "-e", "1"], capture_output=True).returncode else []) + \
        ([] if shutil.which("curl") or shutil.which("wget") else ["curl"])
    for pkg in need:
        done, how = system_install(pkg)
        if not done:
            sys.exit(f"TinyTeX needs {pkg}. Run:\n  {how}\nthen re-run setup.")


def install_tinytex(dest: Path):
    sysname = platform.system()
    if sysname == "Darwin":
        name = "TinyTeX-1-darwin.tar.xz"
    elif sysname == "Linux":
        name = "TinyTeX-1-linuxmusl-x86_64.tar.xz" if musl() else \
            f"TinyTeX-1-linux-{'arm64' if arch() == 'aarch64' else 'x86_64'}.tar.xz"
    else:
        name = "TinyTeX-1-windows.exe"
    log("installing TinyTeX into the cache (~70 MB download)")
    arc = download(TINYTEX_URL + name, CACHE / "downloads" / name)
    tmp = CACHE / "downloads" / "tinytex-unpack"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    if name.endswith(".tar.xz"):
        with tarfile.open(arc) as t:
            t.extractall(tmp, **({"filter": "tar"} if hasattr(tarfile, "tar_filter") else {}))
    else:
        run([arc, "-y", f"-o{tmp}"])  # 7-Zip self-extractor
    root = next(d for d in [tmp, *tmp.iterdir(), *[g for c in tmp.iterdir() if c.is_dir() for g in c.iterdir()]]
                if d.is_dir() and (d / "texmf-dist").exists())
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(root), str(dest))
    shutil.rmtree(tmp, ignore_errors=True)
    arc.unlink()


def ensure_tex(force, prev):
    stamp, tiny = assets_hash(), CACHE / "TinyTeX"
    cands = [tinytex_bin(tiny)] if tiny.exists() else \
        [""] if not force and shutil.which("latexmk") and shutil.which("pdflatex") else []
    for texbin in cands:
        if prev.get("texbin") == texbin and prev.get("tex_ok") == stamp:
            return texbin
        if texbin:
            tinytex_prereqs()
        log("testing LaTeX: " + (texbin or "system install"))
        good, err = smoke_test(texbin)
        if good:
            return texbin
        log("LaTeX could not build the template:\n" + err)
    tinytex_prereqs()
    if not tiny.exists():
        install_tinytex(tiny)
    texbin = tinytex_bin(tiny)
    log("installing TeX packages")
    tlmgr_install(TEX_PKGS, texbin, quiet=False)
    good, err = smoke_test(texbin)
    if not good:
        sys.exit("TinyTeX could not build the template:\n" + err)
    return texbin


# ---------------------------------------------------------------------- voices
def ensure_kokoro(py):
    d = CACHE / "kokoro"
    check = (f"import numpy, onnxruntime as o; numpy.load(r'{d / KOKORO_FILES[1]}'); "
             f"o.InferenceSession(r'{d / KOKORO_FILES[0]}', providers=['CPUExecutionProvider'])")
    for attempt in range(2):
        for f in KOKORO_FILES:
            if not (d / f).exists() or (d / f).stat().st_size == 0:
                download(KOKORO_URL + f, d / f)
        if ok(py, check):
            # a real sentence: catches espeak-ng problems that a model load does not
            r = subprocess.run([str(py), "-c", f"import sys; sys.path.insert(0, r'{SCRIPTS}'); "
                                "import render_lecture as r; r.kokoro_selftest()"], capture_output=True, text=True)
            if r.returncode:
                sys.exit("the offline voice (Kokoro) failed its test sentence:\n" + (r.stderr or r.stdout)[-1500:])
            return
        log("Kokoro model failed to load; downloading it again")
        shutil.rmtree(d, ignore_errors=True)
    sys.exit("Kokoro model could not be loaded")


def clone_spec():
    mlx = platform.system() == "Darwin" and platform.machine() == "arm64"
    # Chatterbox on Apple MLX runs ~real time on Apple silicon; elsewhere the PyTorch package.
    return ("mlx", "3.12", ["mlx-audio", "soundfile"], "import mlx_audio, soundfile") if mlx else \
        ("torch", "3.11", ["chatterbox-tts", "soundfile"], "import chatterbox, soundfile")


def ensure_clone(uv, install=True):
    backend, pyver, pkgs, imp = clone_spec()
    venv = CACHE / "clone-venv"
    py = venv_python(venv)
    if not ok(py, imp):
        if not install:
            return {}
        if not ok(py):
            shutil.rmtree(venv, ignore_errors=True)
            log(f"creating the voice-cloning environment ({backend})")
            run([uv, "venv", "-q", "--python", pyver, venv], env=uv_env())
        log("installing Chatterbox (large download)")
        run([uv, "pip", "install", "-q", "--python", py, *pkgs], env=uv_env())
    if install:
        log("loading the Chatterbox model (first time downloads it)")
        run([py, SCRIPTS / "chatterbox_worker.py", "--preload"])
    return {"clone_python": str(py), "clone_backend": backend}


# --------------------------------------------------------------------- Chinese
def fonts_ok():
    return all((FONTS / f).exists() and (FONTS / f).read_bytes()[:4] == b"OTTO" for f in ZH_FONTS)


def ensure_zh_fonts():
    """Noto Serif SC + Noto Sans SC, regular and bold (~40 MB): the Chinese slide fonts."""
    for f in ZH_FONTS:
        if not ((FONTS / f).exists() and (FONTS / f).read_bytes()[:4] == b"OTTO"):
            download(NOTO_URL + NOTO_PATHS[f] + f, FONTS / f)


ZH_TEX_HELP = ("This LaTeX builds English lectures but not Chinese ones, which need XeLaTeX and the ctex "
               "package. Install them (TeX Live: tlmgr install ctex, with sudo if TeX is root-owned; Debian/"
               "Ubuntu: sudo apt install texlive-xetex texlive-lang-chinese), or switch every lecture to a "
               f"private TinyTeX that installs packages itself: python3 \"{SKILL / 'scripts/lv.py'}\" setup --tinytex")


def zh_stamp():
    return assets_hash(zh=True) + ("+noto" if fonts_ok() else "")


def zh_tex_test(texbin):
    """Build the Chinese template with XeLaTeX (and the personal branding, if any); exit with the
    fix when it cannot be built."""
    log("testing XeLaTeX with the Chinese template")
    good, err = smoke_test(texbin, brand=True, zh=True)
    if not good:
        if (CONFIG / "tex/lecturevideo-brand.sty").exists() and smoke_test(texbin, zh=True)[0]:
            sys.exit(f"{CONFIG / 'tex/lecturevideo-brand.sty'} does not compile with XeLaTeX, so Chinese lectures "
                     f"fail:\n{err}")
        sys.exit(f"{ZH_TEX_HELP}\n{err}")


def ensure_zh_tex(env):
    """First Chinese lecture (init --lang zh, check, render): the fonts (soft: offline, ctex's own
    fonts are used), then one XeLaTeX test, remembered in env.json until the files change."""
    if not fonts_ok():
        try:
            ensure_zh_fonts()
        except SystemExit as e:
            print(f"{e}\nChinese fonts not downloaded; using this system's default Chinese fonts", file=sys.stderr)
    if env.get("tex_zh_ok") != zh_stamp():
        zh_tex_test(env.get("texbin", ""))
        env["tex_zh_ok"] = zh_stamp()
        ENV_FILE.write_text(json.dumps(env, indent=2))


def ensure_zh(uv, py, texbin):
    """setup --zh: the fonts, a XeLaTeX build of the Chinese template, and the offline Chinese
    voice (Kokoro v1.1-zh + misaki's Chinese front end, ~260 MB)."""
    ensure_zh_fonts()
    zh_tex_test(texbin)
    if not ok(py, ZH_IMPORTS):
        log("installing the Chinese text front end (misaki, jieba, pypinyin)")
        run([uv, "pip", "install", "-q", "--python", py, "-r", SCRIPTS / "requirements-zh.txt"], env=uv_env())
        shutil.rmtree(CACHE / "uv-cache", ignore_errors=True)
        if not ok(py, ZH_IMPORTS):
            sys.exit(f"the Chinese text front end did not import in {py}")
    d = CACHE / "kokoro-zh"
    for f, base in KOKORO_ZH_FILES.items():
        if not (d / f).exists() or (d / f).stat().st_size == 0:
            download(base + f, d / f)
    r = subprocess.run([str(py), "-c", f"import sys; sys.path.insert(0, r'{SCRIPTS}'); "
                        "import render_lecture as r; r.kokoro_zh_selftest()"], capture_output=True, text=True)
    if r.returncode:
        sys.exit("the offline Chinese voice failed its test sentence:\n" + (r.stderr or r.stdout)[-1500:])
    return {"zh": True, "tex_zh_ok": zh_stamp()}


def zh_prepare(args):
    """Before check/render of a Chinese lecture: its slide dependencies. (A render that asks for
    the offline Chinese voice installs it itself, once it knows the voice it will use.)"""
    tex = next((Path(x).expanduser() for x in args if x.endswith(".tex")), None)
    if tex and tex.exists() and lecture_lang(tex) == "zh":
        ensure_zh_tex(ensure_ready())


# ----------------------------------------------------------------------- setup
def brand_check(texbin):
    if (CONFIG / "tex" / "lecturevideo-brand.sty").exists():
        good, err = smoke_test(texbin, brand=True)
        log("personal branding compiles" if good else
            f"WARNING: {CONFIG / 'tex/lecturevideo-brand.sty'} does not compile (renders will fail):\n{err}")


def setup(clone=False, tinytex=False, zh=False):
    t0 = time.time()
    CACHE.mkdir(parents=True, exist_ok=True)
    prev = load_env()
    uv = ensure_uv()
    py = ensure_venv(uv)
    ff = ensure_ffmpeg(py)
    texbin = ensure_tex(tinytex, prev)
    ensure_kokoro(py)
    rec = {"version": ENV_VERSION, "python": str(py), "ffmpeg": ff, "texbin": texbin, "tex_ok": assets_hash(),
           "uv": uv, "skill": str(SKILL)}
    rec.update(ensure_clone(uv, install=clone))  # without --clone, only records an existing install
    if prev.get("tex_zh_ok") and prev.get("texbin") == texbin:
        rec["tex_zh_ok"] = prev["tex_zh_ok"]
    if zh or prev.get("zh"):  # once installed, every setup re-checks it, but only --zh may fail on it
        try:
            rec.update(ensure_zh(uv, py, texbin))
        except SystemExit as e:
            if zh:
                raise
            log(f"WARNING: the Chinese extras failed their check and are marked not installed; English "
                f"lectures are unaffected. Repair with: setup --zh\n{e}")
    ENV_FILE.write_text(json.dumps(rec, indent=2))
    brand_check(texbin)
    log(f"READY ({time.time() - t0:.0f}s). LaTeX: {texbin or 'system'}; ffmpeg: {ff}; "
        f"voice cloning: {'yes' if rec.get('clone_python') else 'not installed (setup --clone)'}; "
        f"offline Chinese voice: {'yes' if rec.get('zh') else 'not installed (setup --zh)'}")
    return rec


def ensure_ready():
    env = load_env()
    good = (env.get("version") == ENV_VERSION and ok(env.get("python", "")) and Path(env.get("ffmpeg", "")).exists()
            and (Path(env["texbin"]).exists() if env.get("texbin") else bool(shutil.which("latexmk")))
            and env.get("tex_ok") == assets_hash())
    return env if good else setup()


# --------------------------------------------------------------------- commands
def doctor():
    env, cfg = load_env(), load_config()
    print(f"skill   {SKILL}\ncache   {CACHE}\nconfig  {CONFIG}")
    print(f"setup   {'complete' if env.get('version') == ENV_VERSION else 'not run (any command runs it)'}")
    for k in ("python", "ffmpeg", "texbin", "clone_python"):
        if env.get(k):
            print(f"  {k:<13}{env[k]}  {'ok' if Path(env[k]).exists() else 'MISSING'}")
    if env and not env.get("texbin"):
        print(f"  latex        system: {shutil.which('latexmk') or 'MISSING'}")
    print("config.json  " + (json.dumps(cfg) if cfg else "none (defaults)"))
    status = brand_status()
    print("branding     " + ("not set yet (the agent asks for a logo and a name)" if status == "ask" else status))
    vdirs = [CONFIG / "voices", SKILL / "assets/voices"]
    names = sorted({p.parent.name for d in vdirs for p in d.glob("*/voice.json")})
    print("voices       " + (", ".join(names) or "none") + "  (plus any edge/kokoro voice id)")
    print(f"Chinese      fonts {'ok' if fonts_ok() else 'not yet (fetched by the first Chinese lecture)'}; "
          f"offline voice {'installed' if env.get('zh') else 'not installed (setup --zh)'}")
    from scene import LIB, LIBS, find_browser
    libs = all((LIB / n).exists() for n in LIBS)
    print(f"scenes       libraries {'ok' if libs else 'not yet (fetched by the first elaborated lecture, ~3 MB)'}; "
          f"browser {find_browser(fetch=False) or 'none yet (headless Chrome is fetched when first needed)'}")


def init(name, lang="en"):
    p = Path(name).expanduser()
    if len(Path(name).parts) == 1 and not name.startswith("."):
        p = Path(load_config().get("work_root") or "lecture-videos").expanduser() / name
    p.mkdir(parents=True, exist_ok=True)
    tex = p / "lecture.tex"
    mine, other = (SKILL / "assets" / t for t in (("template-zh.tex", "template.tex") if lang == "zh"
                                                   else ("template.tex", "template-zh.tex")))
    if not tex.exists() or tex.read_bytes() == other.read_bytes():  # new, or the other language's unedited template
        shutil.copy(mine, tex)
    elif lecture_lang(tex) != lang:
        print(f"note: {tex} is an edited {lecture_lang(tex)} lecture; left as it is", file=sys.stderr)
    status = brand_status(p)
    print("branding: " + ("ask - nothing saved yet: ask the user for a logo and a name (SKILL.md, Branding)"
                          if status == "ask" else status))
    print(p.resolve())


def in_venv(script, args):
    env = ensure_ready()
    sys.exit(subprocess.run([env["python"], str(SCRIPTS / script), *args], env=tool_env(env)).returncode)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "setup":
        ap = argparse.ArgumentParser(prog="lv.py setup")
        ap.add_argument("--clone", action="store_true", help="also install voice cloning (large)")
        ap.add_argument("--tinytex", action="store_true", help="use a private TinyTeX even if LaTeX exists")
        ap.add_argument("--zh", action="store_true", help="also install the offline Chinese voice and fonts")
        a = ap.parse_args(rest)
        setup(a.clone, a.tinytex, a.zh)
    elif cmd == "doctor":
        doctor()
    elif cmd == "init":
        ap = argparse.ArgumentParser(prog="lv.py init", description="NAME alone goes under work_root "
                                     "(default ./lecture-videos)")
        ap.add_argument("name")
        ap.add_argument("--lang", choices=["en", "zh"], default="en", help="zh: a Chinese lecture")
        a = ap.parse_args(rest)
        env = ensure_ready()
        if a.lang == "zh":  # catch a LaTeX without Chinese support before any writing starts
            ensure_zh_tex(env)
        init(a.name, a.lang)
    elif cmd == "brand":
        in_venv("brand.py", rest)
    elif cmd == "scene":
        in_venv("scene.py", rest)
    elif cmd == "ingest":
        in_venv("ingest_notes.py", rest)
    elif cmd == "check":
        zh_prepare(rest)
        in_venv("render_lecture.py", [*rest, "--sheet-only"])
    elif cmd == "render":
        zh_prepare(rest)
        in_venv("render_lecture.py", rest)
    else:
        sys.exit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main()
