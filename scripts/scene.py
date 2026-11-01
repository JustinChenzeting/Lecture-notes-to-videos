#!/usr/bin/env python3
"""Animated scenes for elaborated lectures (references/scenes.md).

A scene is a small web page, WORK/scenes/NAME.html, drawn with the kit (assets/scenes/lv.js and
the building blocks in blocks.js) and three.js, anime.js, matter.js, cannon-es, KaTeX or manim-web
(the Manim API in the browser). A headless browser renders it frame by frame and the renderer times
each beat to its narration line. No Node, npm or extra Python packages.

  lv.py scene WORK/scenes/NAME.html   check a scene: its beats and their lengths, script errors,
                                      a still of each beat (NAME-1.png ..., shown on the slides)
                                      and a contact sheet NAME-sheet.png to look at
  lv.py scene --install               fetch the libraries (~6 MB with manim-web) and find a browser

Browser: the installed Chrome, Edge, Chromium or Brave; else Google's headless Chrome for Testing
(100-130 MB, once, into CACHE/scenes/chrome). LV_CHROME=/path/to/browser overrides.
"""
import argparse, asyncio, base64, hashlib, http.server, json, math, os, platform, re, shutil
import subprocess, sys, tempfile, threading, time, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvcommon import CACHE, FONTS, SKILL, WINDOWS, tool_env  # noqa: E402

KIT = SKILL / "assets" / "scenes"
HOME = CACHE / "scenes"
# Pinned libraries: path on npm (served by jsDelivr, unpkg as a fallback) and a SHA-256 prefix.
LIB_VERSION = "1"  # bump with any change below
LIBS = {
    "three.module.js": ("three@0.186.1/build/three.module.js", "9052042d676cb0fd"),
    "three.core.js": ("three@0.186.1/build/three.core.js", "9edde002b066a9a0"),
    "anime.umd.min.js": ("animejs@4.5.0/dist/bundles/anime.umd.min.js", "8d5b3a58a1f64023"),
    "matter.min.js": ("matter-js@0.20.0/build/matter.min.js", "72d30be0f579eb02"),
    "katex.min.js": ("katex@0.19.0/dist/katex.min.js", "103a53763cc033bb"),
    "katex.min.css": ("katex@0.19.0/dist/katex.min.css", "d4ab5b8ee16989b0"),
    **{f"fonts/KaTeX_{n}.woff2": (f"katex@0.19.0/dist/fonts/KaTeX_{n}.woff2", h) for n, h in {
        "AMS-Regular": "0cdd387c9590a1a9", "Caligraphic-Bold": "de7701e42cf1f4cf",
        "Caligraphic-Regular": "5d53e70ad607c235", "Fraktur-Bold": "74444efd593c005e",
        "Fraktur-Regular": "51814d270d06ff02", "Main-Bold": "0f60d1b897938ec9", "Main-BoldItalic": "99cd42a3c072d918",
        "Main-Italic": "97479ca6cce906ab", "Main-Regular": "c2342cd8b869e017", "Math-BoldItalic": "dc47344dbb6cb5b6",
        "Math-Italic": "7af58c5ec8f132a2", "SansSerif-Bold": "e99ae51144bf1232", "SansSerif-Italic": "00b26ac825e20950",
        "SansSerif-Regular": "68e8c73ef42afd3c", "Script-Regular": "036d4e95149b69ff", "Size1-Regular": "6b47c40166b6dbe2",
        "Size2-Regular": "d04c54219f9eaec6", "Size3-Regular": "73d591271b160496", "Size4-Regular": "a4af7d414440a1c1",
        "Typewriter-Regular": "71d517d67827787c"}.items()},
}
# Fetched only when a scene uses them (its HTML names the file): 3D physics, and manim-web, the
# Manim API in the browser (MIT; its npm tarball, ~2.9 MB, unpacked to lib/manim-web, .js files only).
OPTIONAL = {
    "cannon-es.js": ("cannon-es@0.20.0/dist/cannon-es.js", "f0700cbd3a482954"),
    "3Dmol-min.js": ("3dmol@2.5.5/build/3Dmol-min.js", "f7cc78921ae72e76"),
    "smiles-drawer.min.js": ("smiles-drawer@2.4.1/dist/smiles-drawer.min.js", "6b0397cd52a708ee"),
}
MANIM_WEB = ("https://registry.npmjs.org/manim-web/-/manim-web-0.39.4.tgz",
             "63ca4194e6d2dbdf3604f02dfcc22fdd40918b97cf840a8abe6f66fdf92bd3c3")
LIB = HOME / f"lib-{LIB_VERSION}"
CDN = ["https://cdn.jsdelivr.net/npm/", "https://unpkg.com/"]
CFT = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
W, H = 1920, 1080          # scenes are authored at this size
STILL_H = 720              # height of the stills shown on the slides
GAP = 0.6                  # seconds between beats when there is no narration yet (checks, stills)


def say(msg):
    print(msg, flush=True)


class SceneError(Exception):
    pass


# ------------------------------------------------------------------ installation
def _sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _fetch(url, dst: Path):
    from lv import download  # stdlib downloader with retries and a curl fallback
    return download(url, dst)


def ensure_libs(html_text=""):
    """The pinned libraries in CACHE/scenes/lib-N (about 3 MB, fetched once), plus the optional
    ones a scene names (cannon-es, manim-web)."""
    wanted = {**LIBS, **{n: v for n, v in OPTIONAL.items() if n in html_text or html_text == "*"}}
    if "manim" in html_text or html_text == "*":
        ensure_manim_web()
    missing = [n for n, (_, h) in wanted.items() if not (LIB / n).exists() or _sha(LIB / n) != h]
    if not missing:
        return LIB
    say(f"scenes: fetching {len(missing)} library files (once)")
    for n in missing:
        path, h = wanted[n]
        for base in CDN:
            try:
                _fetch(base + path, LIB / n)
            except SystemExit:
                continue
            if _sha(LIB / n) == h:
                break
            (LIB / n).unlink()
        else:
            sys.exit(f"scenes: could not fetch a verified copy of {path}. Check the internet connection and run "
                     f"`lv.py scene --install` again.")
    return LIB


def ensure_manim_web():
    """manim-web's browser build in lib/manim-web (fetched once, checked against its SHA-256)."""
    import tarfile
    dest = LIB / "manim-web"
    if (dest / "manim-web.browser.js").exists() and (dest / ".sha").exists() and (dest / ".sha").read_text() == MANIM_WEB[1]:
        return dest
    say("scenes: fetching manim-web, the Manim API for the browser (~2.9 MB, once)")
    tgz = _fetch(MANIM_WEB[0], HOME / "manim-web.tgz")
    if hashlib.sha256(tgz.read_bytes()).hexdigest() != MANIM_WEB[1]:
        tgz.unlink()
        sys.exit("scenes: the manim-web download did not match its checksum; run `lv.py scene --install` again")
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    with tarfile.open(tgz) as tf:
        for m in tf.getmembers():
            if m.isfile() and m.name.startswith("package/dist/") and m.name.endswith(".js") and not m.name.endswith(".d.ts"):
                rel = Path(m.name[len("package/dist/"):])
                if ".." in rel.parts:
                    continue
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(tf.extractfile(m).read())
    tgz.unlink()
    (dest / ".sha").write_text(MANIM_WEB[1])
    return dest


def _browsers():
    """Installed Chromium-family browsers, most likely first."""
    if os.environ.get("LV_CHROME"):
        yield Path(os.environ["LV_CHROME"])
    if sys.platform == "darwin":
        for root in (Path("/Applications"), Path.home() / "Applications"):
            for app, exe in (("Google Chrome", "Google Chrome"), ("Microsoft Edge", "Microsoft Edge"),
                             ("Chromium", "Chromium"), ("Brave Browser", "Brave Browser")):
                yield root / f"{app}.app/Contents/MacOS/{exe}"
    elif WINDOWS:
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = Path(os.environ.get(env, "C:/missing"))
            yield base / "Google/Chrome/Application/chrome.exe"
            yield base / "Microsoft/Edge/Application/msedge.exe"
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
                     "microsoft-edge-stable", "brave-browser"):
            if shutil.which(name):
                yield Path(shutil.which(name))


def _shell_platform():
    m = platform.machine().lower()
    if sys.platform == "darwin":
        return "mac-arm64" if m in ("arm64", "aarch64") else "mac-x64"
    if WINDOWS:
        return "win64" if m.endswith("64") else "win32"
    return "linux-arm64" if m in ("arm64", "aarch64") else "linux64"


def _shell_exe():
    plat = _shell_platform()
    return HOME / "chrome" / f"chrome-headless-shell-{plat}" / ("chrome-headless-shell.exe" if WINDOWS
                                                                 else "chrome-headless-shell")


def fetch_shell():
    """Google's headless Chrome for Testing, unpacked into CACHE/scenes/chrome (permissions kept)."""
    import urllib.request
    plat = _shell_platform()
    with urllib.request.urlopen(CFT, timeout=60) as r:
        stable = json.load(r)["channels"]["Stable"]
    url = next((d["url"] for d in stable["downloads"].get("chrome-headless-shell", []) if d["platform"] == plat), None)
    if not url:
        sys.exit(f"scenes: no headless Chrome is published for {plat}. Install Chrome or Chromium, or set LV_CHROME.")
    say(f"scenes: no Chrome or Edge found; fetching Google's headless Chrome {stable['version']} "
        f"(~100-130 MB, once)")
    z = _fetch(url, HOME / "chrome" / f"{plat}.zip")
    with zipfile.ZipFile(z) as zf:
        for info in zf.infolist():
            out = zf.extract(info, HOME / "chrome")
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                os.chmod(out, mode)
    z.unlink()
    return _shell_exe()


def find_browser(fetch=True):
    for p in _browsers():
        if p.is_file():
            return p
    shell = _shell_exe()
    if shell.is_file():
        return shell
    return fetch_shell() if fetch else None


def ensure_kit():
    ensure_libs("*")
    return find_browser()


def kit_hash():
    return hashlib.sha1(b"".join((KIT / f).read_bytes() for f in ("lv.js", "blocks.js", "quantum.js", "materials.js") if (KIT / f).exists())
                        + LIB_VERSION.encode() + MANIM_WEB[1].encode()).hexdigest()[:12]


# ------------------------------------------------------------------ local server
def _texfont(name, _cache={}):  # noqa: B006 - small memo of kpsewhich lookups
    if name not in _cache:
        r = subprocess.run(["kpsewhich", name], capture_output=True, text=True, env=tool_env())
        _cache[name] = r.stdout.strip() or None
    return _cache[name]


def serve(root: Path):
    """Serve the scene folder at /, the libraries at /lib, the kit at /kit, the Chinese fonts at
    /fonts and TeX's own fonts at /texfont, on 127.0.0.1 only."""
    routes = {"/lib/": LIB, "/kit/": KIT, "/fonts/": FONTS}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            if path.startswith("/texfont/"):
                return _texfont(Path(path).name) or str(root / "__missing__")
            for prefix, d in routes.items():
                if path.startswith(prefix):
                    return str(d / Path(path[len(prefix):]))
            return str(root / path.lstrip("/"))

        def log_message(self, *a):
            pass

    Handler.extensions_map = {**Handler.extensions_map, ".js": "text/javascript", ".mjs": "text/javascript",
                              ".otf": "font/otf", ".woff2": "font/woff2"}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# -------------------------------------------------------------- browser control
class Browser:
    """A headless browser driven over the DevTools protocol (aiohttp's websocket client)."""

    def __init__(self, exe: Path):
        self.exe, self.n, self.wait, self.errors = exe, 0, {}, []

    async def __aenter__(self):
        import aiohttp
        self.prof = tempfile.mkdtemp(prefix="lv-chrome-")
        args = [str(self.exe), "--remote-debugging-port=0", f"--user-data-dir={self.prof}", "--no-first-run",
                "--no-default-browser-check", "--hide-scrollbars", "--mute-audio", "--disable-extensions",
                "--enable-unsafe-swiftshader", "--force-device-scale-factor=1", "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows"]
        if "headless-shell" not in self.exe.name:
            args.insert(1, "--headless=new")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            args.append("--no-sandbox")  # Chrome refuses to run as root otherwise (containers)
        self.proc = subprocess.Popen(args + ["about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        port_file = Path(self.prof) / "DevToolsActivePort"
        for _ in range(300):
            if port_file.exists() and len(port_file.read_text().split()) >= 2:
                break
            if self.proc.poll() is not None:
                raise SceneError(f"the browser {self.exe} did not start:\n"
                                 + self.proc.stderr.read().decode(errors="replace")[-1500:])
            await asyncio.sleep(0.05)
        else:
            raise SceneError(f"the browser {self.exe} did not open its control port")
        port, path = port_file.read_text().split()[:2]
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(f"ws://127.0.0.1:{port}{path}", max_msg_size=0)
        self.pump = asyncio.create_task(self._pump())
        tid = (await self.call("Target.createTarget", url="about:blank"))["targetId"]
        self.sid = (await self.call("Target.attachToTarget", targetId=tid, flatten=True))["sessionId"]
        await self.call("Runtime.enable", self.sid)
        await self.call("Page.enable", self.sid)
        await self.call("Emulation.setDeviceMetricsOverride", self.sid, width=W, height=H, deviceScaleFactor=1,
                        mobile=False)
        return self

    async def __aexit__(self, *exc):
        self.pump.cancel()
        await self.ws.close()
        await self.session.close()
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.prof, ignore_errors=True)

    async def _pump(self):
        async for m in self.ws:
            d = json.loads(m.data)
            if "id" in d and d["id"] in self.wait:
                self.wait.pop(d["id"]).set_result(d)
            elif d.get("method") == "Runtime.exceptionThrown":
                e = d["params"]["exceptionDetails"]
                self.errors.append((e.get("exception", {}).get("description") or e.get("text", "error"))
                                   + f" (line {e.get('lineNumber', 0) + 1})")
            elif d.get("method") == "Runtime.consoleAPICalled" and d["params"]["type"] == "error":
                self.errors.append(" ".join(str(a.get("value", a.get("description", ""))) for a in d["params"]["args"]))
            elif d.get("method") == "Log.entryAdded" and d["params"]["entry"]["level"] == "error":
                e = d["params"]["entry"]
                url = e.get("url", "")
                if not url.endswith("/favicon.ico"):  # browsers ask for one on their own
                    self.errors.append(e["text"] + (f": {url.split('/', 3)[-1]}" if url else ""))

    async def call(self, method, sid=None, **params):
        self.n += 1
        fut = asyncio.get_running_loop().create_future()
        self.wait[self.n] = fut
        msg = {"id": self.n, "method": method, "params": params}
        if sid:
            msg["sessionId"] = sid
        await self.ws.send_str(json.dumps(msg))
        d = await asyncio.wait_for(fut, 120)
        if "error" in d:
            raise SceneError(f"{method}: {d['error'].get('message')}")
        return d["result"]

    async def js(self, expr, wait=False):
        r = await self.call("Runtime.evaluate", self.sid, expression=expr, returnByValue=True, awaitPromise=wait)
        if "exceptionDetails" in r:
            e = r["exceptionDetails"]
            raise SceneError((e.get("exception", {}).get("description") or e.get("text", "error")).splitlines()[0])
        return r["result"].get("value")

    async def open(self, url, timeout=30):
        await self.call("Log.enable", self.sid)
        await self.call("Page.navigate", self.sid, url=url)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if await self.js("!!(window.lv && window.lv.ready)"):
                return await self.js("lv.info()")
            if self.errors or await self.js("window.lvError || ''"):
                break
            await asyncio.sleep(0.1)
        msg = "\n  ".join(self.errors or [await self.js("window.lvError || ''") or
                                         "the scene never finished loading: does it end with LV.done()?"])
        raise SceneError("the scene did not start:\n  " + msg)

    async def shot(self, out: Path, height):
        r = await self.call("Page.captureScreenshot", self.sid, format="png", optimizeForSpeed=True,
                            captureBeyondViewport=False, clip={"x": 0, "y": 0, "width": W, "height": H,
                                                               "scale": height / H})
        out.write_bytes(base64.b64decode(r["data"]))


# ----------------------------------------------------------------------- scenes
def scene_files(html: Path):
    """Files whose change invalidates the stills: the page and the other assets beside it."""
    stem = html.stem
    own = re.compile(rf"{re.escape(stem)}-(\d+|sheet)\.png$|{re.escape(stem)}\.json$")
    return [html] + sorted(p for p in html.parent.iterdir()
                           if p.is_file() and p != html and p.suffix != ".html" and not re.match(r".+-(\d+|sheet)\.png$", p.name)
                           and not own.match(p.name) and not p.name.endswith(".json"))


def scene_key(html: Path):
    h = hashlib.sha1(kit_hash().encode())
    for p in scene_files(html):
        h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()[:16]


def default_plan(nat_ms):
    starts, s = [], 0.0
    for d in nat_ms:
        starts.append(s)
        s += d / 1000 + GAP
    return starts, [d / 1000 + GAP for d in nat_ms]


async def _check(html: Path, browser: Path, sheet=True):
    srv = serve(html.parent)
    url = f"http://127.0.0.1:{srv.server_address[1]}/{html.name}"
    try:
        async with Browser(browser) as b:
            info = await b.open(url)
            nat = info["beats"]
            starts, lens = default_plan(nat)
            stills = []
            for i, (s, d) in enumerate(zip(starts, lens)):
                await b.js(f"lv.seek({s + d - 0.05})", wait=True)
                out = html.with_name(f"{html.stem}-{i + 1}.png")
                await b.shot(out, STILL_H)
                stills.append(out)
            frames = []
            if sheet:
                total = starts[-1] + lens[-1]
                await b.js(f"lv.plan({json.dumps(starts)}, {json.dumps(lens)})", wait=True)
                tmp = Path(tempfile.mkdtemp(prefix="lv-sheet-"))
                for k in range(12):
                    t = total * (k + 0.5) / 12
                    await b.js(f"lv.seek({t})", wait=True)
                    await b.shot(tmp / f"{k:02d}.png", 360)
                    beat = max(i for i, s in enumerate(starts) if s <= t)
                    frames.append((tmp / f"{k:02d}.png", f"{t:.1f}s  beat {beat + 1}"))
            if b.errors:
                raise SceneError("script errors while playing:\n  " + "\n  ".join(dict.fromkeys(b.errors)))
    finally:
        srv.shutdown()
    if frames:
        _sheet(frames, html.with_name(f"{html.stem}-sheet.png"))
        shutil.rmtree(frames[0][0].parent, ignore_errors=True)
    return nat, stills


def _sheet(frames, out: Path, cols=4):
    from PIL import Image, ImageDraw
    ims = [(Image.open(p).convert("RGB"), label) for p, label in frames]
    w, h, gap = ims[0][0].width, ims[0][0].height, 6
    rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), "white")
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(ims):
        x, y = gap + (i % cols) * (w + gap), gap + (i // cols) * (h + gap)
        sheet.paste(im, (x, y))
        d.rectangle([x, y + h - 18, x + 8 + 7 * len(label), y + h], fill="black")
        d.text((x + 4, y + h - 15), label, fill="white")
    sheet.save(out)


def prepare(html: Path, force=False, sheet=False, quiet=False):
    """Check a scene and write its stills; cached by content. Returns the beats' own lengths (ms)."""
    html = html.resolve()
    if not html.exists():
        sys.exit(f"no scene file {html}: write it from a template in {KIT / 'examples'} (references/scenes.md)")
    rec_file = html.with_suffix(".json")
    key = scene_key(html)
    try:
        rec = json.loads(rec_file.read_text())
    except (OSError, ValueError):
        rec = {}
    stills_ok = all(html.with_name(f"{html.stem}-{i + 1}.png").exists() for i in range(len(rec.get("beats", []))))
    if not force and rec.get("key") == key and stills_ok and (not sheet or html.with_name(f"{html.stem}-sheet.png").exists()):
        return rec["beats"]
    ensure_libs(html.read_text(encoding="utf-8", errors="replace"))
    browser = find_browser()
    t0 = time.time()
    try:
        nat, _ = asyncio.run(_check(html, browser, sheet))
    except SceneError as e:
        sys.exit(f"scene {html.name}: {e}")
    rec_file.write_text(json.dumps({"key": key, "beats": nat}))
    for old in html.parent.glob(f"{html.stem}-*.png"):  # stills of beats that no longer exist
        m = re.fullmatch(rf"{re.escape(html.stem)}-(\d+)\.png", old.name)
        if m and int(m.group(1)) > len(nat):
            old.unlink()
    if not quiet:
        say(f"scene {html.stem}: {len(nat)} beats, own lengths "
            + ", ".join(f"{d / 1000:.1f}s" for d in nat) + f"  ({time.time() - t0:.1f}s)")
    return nat


async def _frames(html: Path, browser: Path, starts, lens, fps, height, out: Path):
    srv = serve(html.parent)
    url = f"http://127.0.0.1:{srv.server_address[1]}/{html.name}"
    shots = []
    try:
        async with Browser(browser) as b:
            await b.open(url)
            await b.js(f"lv.plan({json.dumps(starts)}, {json.dumps(lens)})", wait=True)  # may rebuild (manim-web)
            for i, (s, d) in enumerate(zip(starts, lens)):
                n = max(1, round(d * fps))
                beat = []
                for j in range(n):
                    p = out / f"b{i + 1:02d}-{j:05d}.png"
                    await b.js(f"lv.seek({s + j / fps})", wait=True)
                    await b.shot(p, height)
                    beat.append(p)
                shots.append(beat)
            if b.errors:
                raise SceneError("script errors while playing:\n  " + "\n  ".join(dict.fromkeys(b.errors)))
    finally:
        srv.shutdown()
    return shots


def render_frames(html: Path, lens, fps, height, out: Path):
    """Frames for each beat, beat i lasting lens[i] seconds: a list (one per beat) of PNG lists.
    Cached by the scene's content and the timing."""
    html = html.resolve()
    starts, s = [], 0.0
    for d in lens:
        starts.append(round(s, 4))
        s += d
    key = hashlib.sha1(json.dumps([scene_key(html), [round(x, 3) for x in lens], fps, height]).encode()).hexdigest()[:16]
    stamp = out / "key.txt"
    if stamp.exists() and stamp.read_text() == key:
        shots = [sorted(out.glob(f"b{i + 1:02d}-*.png")) for i in range(len(lens))]
        if all(len(b) == max(1, round(d * fps)) for b, d in zip(shots, lens)):
            return shots
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    ensure_libs(html.read_text(encoding="utf-8", errors="replace"))
    t0 = time.time()
    try:
        shots = asyncio.run(_frames(html, find_browser(), starts, [round(x, 4) for x in lens], fps, height, out))
    except SceneError as e:
        sys.exit(f"scene {html.name}: {e}")
    stamp.write_text(key)
    n = sum(map(len, shots))
    say(f"scene {html.stem}: {n} frames ({s:.1f}s of video) in {time.time() - t0:.0f}s")
    return shots


def main():
    ap = argparse.ArgumentParser(prog="lv.py scene", description=__doc__.split("\n\n")[0])
    ap.add_argument("scene", nargs="?", help="WORK/scenes/NAME.html")
    ap.add_argument("--install", action="store_true", help="fetch the libraries and find or fetch a browser")
    a = ap.parse_args()
    if a.install or not a.scene:
        ensure_libs("*")
        say(f"scenes: libraries in {LIB}\nscenes: browser {find_browser()}")
        return
    html = Path(a.scene).expanduser()
    prepare(html, force=True, sheet=True)
    stills = sorted(html.parent.glob(f"{html.stem}-[0-9]*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
    say("stills: " + ", ".join(p.name for p in stills) + "  (one per beat, shown on the slides)")
    say(f"sheet:  {html.with_name(html.stem + '-sheet.png')}  (look at it)")


if __name__ == "__main__":
    main()
