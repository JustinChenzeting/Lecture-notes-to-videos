#!/usr/bin/env python3
"""lecture-notes-to-video: one entry point for every step. Standard library only (Python 3.8+).

  python3 lv.py setup [--clone] [--tinytex]   install or repair everything (idempotent)
  python3 lv.py doctor                        report what is installed; changes nothing
  python3 lv.py init NAME|DIR                 new work folder holding lecture.tex (from the template)
  python3 lv.py ingest NOTES... --out DIR     prepare notes for reading  [--visual 3,7-9]
  python3 lv.py check DIR/lecture.tex         compile + contact sheets + layout warnings, no audio
  python3 lv.py render DIR/lecture.tex [OUT.mp4] [--voice NAME] [--tts edge|kokoro|say|chatterbox]
                                              [--rate +10%] [--height 720] [--no-subs]
                                              (also writes OUT.srt + OUT.vtt and a subtitle track)

init, ingest, check and render run setup automatically the first time, so a new machine
needs no separate install step. Setup downloads (once, into LECTURE_VIDEO_CACHE):
  uv + Python 3.12 venv (edge-tts, kokoro-onnx, pypdfium2, Pillow, imageio-ffmpeg)   ~150 MB
  Kokoro British voices for offline narration                                         ~115 MB
  TinyTeX, only when no working LaTeX is installed                                    ~250 MB
  --clone: a voice-cloning env (Chatterbox; MLX on Apple silicon, PyTorch elsewhere)   ~2-4 GB
--tinytex forces a private TinyTeX even when a system LaTeX exists.
"""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvcommon import (CACHE, CONFIG, ENV_FILE, ENV_VERSION, SKILL, WINDOWS, compile_latex,  # noqa: E402
                      latex_errors, load_config, load_env, tlmgr_install, tool_env, venv_python)

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
def assets_hash():
    h = hashlib.sha1()
    for f in ("lecturevideo.sty", "beamerthemelecturevideo.sty", "template.tex"):
        h.update((SKILL / "assets" / f).read_bytes())
    return h.hexdigest()[:12]


def tinytex_bin(root: Path):
    return str(next(p for p in sorted((root / "bin").iterdir()) if p.is_dir()))


def smoke_test(texbin, brand=False):
    """Compile the template in a scratch folder: the real test of a TeX install."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tex = Path(d) / "lecture.tex"
        shutil.copy(SKILL / "assets/template.tex", tex)
        good, logtext = compile_latex(tex, env={"texbin": texbin}, brand=brand)
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


# ----------------------------------------------------------------------- setup
def brand_check(texbin):
    if (CONFIG / "tex" / "lecturevideo-brand.sty").exists():
        good, err = smoke_test(texbin, brand=True)
        log("personal branding compiles" if good else
            f"WARNING: {CONFIG / 'tex/lecturevideo-brand.sty'} does not compile (renders will fail):\n{err}")


def setup(clone=False, tinytex=False):
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
    ENV_FILE.write_text(json.dumps(rec, indent=2))
    brand_check(texbin)
    log(f"READY ({time.time() - t0:.0f}s). LaTeX: {texbin or 'system'}; ffmpeg: {ff}; "
        f"voice cloning: {'yes' if rec.get('clone_python') else 'not installed (setup --clone)'}")
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
    brand = CONFIG / "tex/lecturevideo-brand.sty"
    print("branding     " + (str(brand) if brand.exists() else "none (built-in theme)"))
    vdirs = [CONFIG / "voices", SKILL / "assets/voices"]
    names = sorted({p.parent.name for d in vdirs for p in d.glob("*/voice.json")})
    print("voices       " + (", ".join(names) or "none") + "  (plus any edge/kokoro voice id)")


def init(name):
    p = Path(name).expanduser()
    if len(Path(name).parts) == 1 and not name.startswith("."):
        p = Path(load_config().get("work_root") or "lecture-videos").expanduser() / name
    p.mkdir(parents=True, exist_ok=True)
    tex = p / "lecture.tex"
    if not tex.exists():
        shutil.copy(SKILL / "assets/template.tex", tex)
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
        a = ap.parse_args(rest)
        setup(a.clone, a.tinytex)
    elif cmd == "doctor":
        doctor()
    elif cmd == "init":
        if len(rest) != 1 or rest[0].startswith("-"):
            sys.exit("usage: lv.py init NAME|DIR   (NAME alone goes under work_root, default ./lecture-videos)")
        ensure_ready()
        init(rest[0])
    elif cmd == "ingest":
        in_venv("ingest_notes.py", rest)
    elif cmd == "check":
        in_venv("render_lecture.py", [*rest, "--sheet-only"])
    elif cmd == "render":
        in_venv("render_lecture.py", rest)
    else:
        sys.exit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main()
