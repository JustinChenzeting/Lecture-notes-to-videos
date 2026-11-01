#!/usr/bin/env python3
"""Render a narrated lecture video from a beamer .tex that uses lecturevideo.sty.

The .tex is the only thing an agent writes. Narration lives in the slides as
\\say<overlay>{...}; silent holds as \\wait<overlay>{seconds}. LaTeX itself writes a
page-accurate narration map (<job>.narr), so no fragile source parsing is needed.

Pipeline: latexmk -> <job>.narr + PDF -> PNG pages -> TTS (cached by text hash)
-> one audio track + one image-sequence video (single encode) -> MP4.

Run it through lv.py (which supplies the environment):
  lv.py render LECTURE.tex [OUT.mp4] [--tts edge|kokoro|say|chatterbox] [--voice V]
               [--rate +10%] [--height 720] [--pad 0.4] [--lexicon F] [--sheet]
  lv.py check  LECTURE.tex          # compile + contact sheets + layout warnings, no audio
--voice also takes a named profile (voices/<name>/voice.json in the work folder, the config
folder or the skill's assets), which sets the engine, voice, rate and title-page credit.
Defaults for --voice/--tts/--rate/--height/output folder come from the config.json, if any.
"""
import argparse, asyncio, difflib, hashlib, importlib, json, math, os, platform, re, subprocess, sys, tempfile, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvcommon import (CACHE, CONFIG, HAN, SKILL, brand_status, compile_latex, ffmpeg, latex_errors,  # noqa: E402
                      lecture_lang, load_config, load_env, tex_source)

SR = 24000
DEFAULT_RATE = "+10%"
DEFAULT_VOICE = {"edge": "en-GB-SoniaNeural", "kokoro": "bf_emma", "say": "Shelley (English (UK))"}
# edge-tts can stall forever on an open connection (its own timeouts miss this), so each line
# gets 30 s plus 0.1 s per character, then a retry, then the offline fallback.
EDGE_LIMIT = 30
# Chinese lectures (\usepackage[zh]{lecturevideo}, references/chinese.md). Yunxi was chosen by ear.
ZH_RATE = "+0%"
ZH_VOICE = {"edge": "zh-CN-YunxiNeural", "kokoro": "zm_009", "say": "Tingting"}
ZH_SPM = 265  # spoken syllables a minute, zh-CN-YunxiNeural at +0% (measured)
KOKORO_ZH = ["kokoro-v1.1-zh.int8.onnx", "voices-v1.1-zh.bin", "config.json"]  # in CACHE/kokoro-zh
FF = ffmpeg()


def voice_dirs(work: Path):
    return [work / "voices", CONFIG / "voices", SKILL / "assets/voices"]


def find_profile(name, work: Path):
    """'Prof. Smith' / 'smith' -> the matching voices/<dir>/voice.json, or None."""
    norm = lambda t: re.sub(r"[^a-z0-9_]+", " ", t.lower()).strip()  # noqa: E731
    for d in voice_dirs(work):
        for f in sorted(d.glob("*/voice.json")):
            prof = json.loads(f.read_text())
            if norm(name) in {norm(f.parent.name), norm(prof.get("label", ""))} | {norm(x) for x in prof.get("aliases", [])}:
                prof["dir"] = f.parent
                return prof
    return None


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


# --------------------------------------------------------------------- build
def compile_tex(tex: Path, credit="", engine="pdf"):
    pre = [f"-usepretex=\\def\\lvvoicecredit{{{credit}}}"] if credit else []
    stamp = tex.parent / f"{tex.stem}_build" / "credit.txt"  # latexmk can't see a pretex change
    key = credit if engine == "pdf" else f"{credit}|{engine}"
    force = ["-g"] if not stamp.exists() or stamp.read_text() != key else []
    stamp.write_text(key)
    good, log = compile_latex(tex, [*force, *pre], engine=engine)
    if not good:
        sys.exit("LaTeX failed:\n" + latex_errors(log))
    return log


def layout_warnings(log: str):
    """Overflowing frames and lines, from the LaTeX log: a check that needs no eyes."""
    out = []
    for m in re.finditer(r"Overfull \\(v|h)box \(([\d.]+)pt too (?:high|wide)\)[^\n]*?(?:lines? (\d+)(?:--(\d+))?)?\n", log):
        kind, pt, line = m.group(1), float(m.group(2)), m.group(3)
        if (kind == "v" and pt > 4) or (kind == "h" and pt > 8):
            out.append(f"{'content too tall' if kind == 'v' else 'line too wide'} by {pt:.0f}pt"
                       + (f" near line {line}" if line else ""))
    return out


def read_narr(tex: Path, npages: int, lang="en"):
    """Return per-page (kind, value, event_id) with kind 'say' | 'wait', or None, and the pages'
    metadata {"frame": {page: frame}, "cam": {page: (x, y, zoom)}, "scene": {page: (name, beat)}}.

    Each record is page|kind|frame|ordinal|overlay-spec|text. The event id is
    (frame, ordinal, spec, text); only range specs (<2-13>) may span several pages.
    Chinese narration may write a percent sign as \\% (35\\% reads 百分之三十五)."""
    pages = [None] * npages
    meta = {"frame": {}, "cam": {}, "scene": {}}
    narr = (tex.parent / f"{tex.stem}.narr").read_text(encoding="utf-8", errors="replace")
    for n, line in enumerate(narr.splitlines(), 1):
        try:
            p, kind, frame, ordn, spec, val = line.split("|", 5)
            p = int(p) - 1
            assert 0 <= p < npages and kind in ("say", "wait", "cam", "scene")
        except (ValueError, AssertionError):
            sys.exit(f".narr line {n} malformed: {line[:80]}")
        meta["frame"][p] = frame
        if kind == "cam":  # \lvzoom: x, y as fractions of the slide, zoom 1-3
            try:
                x, y, z = (float(v) for v in val.split(","))
            except ValueError:
                sys.exit(f"page {p + 1}: \\lvzoom needs three numbers, x, y (0-1) and a zoom (1-3): {val}")
            meta["cam"][p] = (min(max(x, 0), 1), min(max(y, 0), 1), min(max(z, 1), 3))
            continue
        if kind == "scene":  # \lvscene: beat k of scenes/<name>.html on overlay k
            meta["scene"][p] = (val.strip(), int(re.sub(r"\D", "", spec) or 1))
            continue
        val = " ".join(val.replace("\\ ", " ").split())
        if lang == "zh" and kind == "say":
            val = val.replace("\\%", "%")
        if kind == "wait":
            val = float(val)
            if not math.isfinite(val) or val <= 0:
                sys.exit(f"page {p + 1}: \\wait needs a positive number of seconds")
        if pages[p] is None:
            span = "-" in spec or "," in spec
            pages[p] = (kind, val, (frame, ordn, spec, val) if span else (p,))
        elif pages[p][0] == kind == "say":  # two \say on one page: speak both, in order
            pages[p] = ("say", pages[p][1] + " " + val, pages[p][2] + (val,))
        else:
            sys.exit(f"page {p + 1}: conflicting \\say/\\wait on the same page")
    return pages, meta


def rasterize(pdf: Path, build: Path, height: int):
    """PDF -> p-001.png ... at the video height (pypdfium2; no poppler needed)."""
    import pypdfium2 as pdfium
    stamp = build / "raster.sha"
    key = hashlib.sha1(pdf.read_bytes() + str(height).encode()).hexdigest()
    pngs = sorted(build.glob("p-*.png"))
    doc = pdfium.PdfDocument(str(pdf))
    if stamp.exists() and stamp.read_text() == key and len(pngs) == len(doc):
        return pngs  # slides unchanged since the last run
    for old in pngs:
        old.unlink()
    size = None
    for i in range(len(doc)):
        page = doc[i]
        img = page.render(scale=height / page.get_height()).to_pil().convert("RGB")
        size = size or (img.width + img.width % 2, height)
        if img.size != size:  # identical, even dimensions for libx264
            img = img.resize(size)
        img.save(build / f"p-{i + 1:03d}.png")
    stamp.write_text(key)
    return sorted(build.glob("p-*.png"))


def contact_sheets(pngs, build: Path, per=12, cols=3):
    """Numbered 3-wide grids of page thumbnails, in page order, for a quick visual check."""
    from PIL import Image, ImageDraw
    for old in build.glob("sheet-*.png"):
        old.unlink()
    sheets, tw, gap = [], 480, 6
    for k in range(0, len(pngs), per):
        thumbs = []
        for p in pngs[k:k + per]:
            im = Image.open(p).convert("RGB")
            thumbs.append(im.resize((tw, round(im.height * tw / im.width))))
        th, rows = thumbs[0].height, math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap), "white")
        d = ImageDraw.Draw(sheet)
        for i, t in enumerate(thumbs):
            x, y = gap + (i % cols) * (tw + gap), gap + (i // cols) * (th + gap)
            sheet.paste(t, (x, y))
            yb = y + th - 16  # page number at the bottom left, clear of titles and logos
            d.rectangle([x, yb, x + 38, yb + 16], fill="black")
            d.text((x + 4, yb + 3), f"p{k + i + 1}", fill="white")
        out = build / f"sheet-{k // per + 1}.png"
        sheet.save(out)
        sheets.append(out)
    return sheets


# ------------------------------------------------------ camera moves and fades
# Both work on the shot list: (png, seconds, page index or None), and insert short frames.
FPS = 24          # the video's frame rate (the final encode resamples to it)
CAM_MOVE = 0.8    # seconds for a camera move (\lvzoom)


def _ease(u):
    return u * u * (3 - 2 * u)


def apply_camera(shots, cams, frames, pdf: Path, build: Path):
    """\\lvzoom: crop pages to the camera (rendered sharp at the zoom), moving smoothly whenever the
    camera changes within a frame. A new frame starts on the whole slide."""
    if not cams:
        return shots
    import pypdfium2 as pdfium
    from PIL import Image
    d = build / "cam"
    d.mkdir(exist_ok=True)
    doc, big = pdfium.PdfDocument(str(pdf)), {}
    W, H = Image.open(shots[0][0]).size

    def hires(p, z):  # page p rendered at z times the video size (z = 1, 2 or 3)
        z = min(3, math.ceil(z))
        f = d / f"hi-{p + 1:03d}-{z}.png"
        if (p, z) not in big:
            if not f.exists():
                page = doc[p]
                page.render(scale=H * z / page.get_height()).to_pil().convert("RGB").resize((W * z, H * z)).save(f)
            big[(p, z)] = Image.open(f)
        return big[(p, z)], z

    def crop(p, cam, zmax):
        x, y, z = cam
        img, k = hires(p, zmax)
        vw, vh = W / z, H / z
        cx, cy = min(max(x * W, vw / 2), W - vw / 2), min(max(y * H, vh / 2), H - vh / 2)
        box = tuple(round(v * k) for v in (cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2))
        return img.crop(box).resize((W, H), Image.LANCZOS)

    def still(p, cam, zmax, tag):
        f = d / f"c-{p + 1:03d}-{tag}.png"
        if not f.exists():
            crop(p, cam, zmax).save(f)
        return f

    full = (0.5, 0.5, 1.0)
    out, prev, prev_frame = [], full, None
    for png, dur, p in shots:
        if p is None:
            out.append((png, dur, p))
            prev, prev_frame = full, None
            continue
        cam = cams.get(p, full)
        if frames.get(p) != prev_frame:
            prev = full
        prev_frame = frames.get(p)
        zmax = max(prev[2], cam[2])
        if cam != prev and dur > 0.3:  # move: log-interpolate the zoom so it feels even
            n = max(2, round(min(CAM_MOVE, dur / 2) * FPS))
            for k in range(1, n + 1):
                u = _ease(k / n)
                c = (prev[0] + (cam[0] - prev[0]) * u, prev[1] + (cam[1] - prev[1]) * u,
                     math.exp(math.log(prev[2]) + (math.log(cam[2]) - math.log(prev[2])) * u))
                out.append((still(p, c, zmax, "m" + hashlib.sha1(repr((c, zmax)).encode()).hexdigest()[:10]),
                            1 / FPS, None))
            dur -= n / FPS
        if cam != full:
            png = still(p, cam, cam[2], hashlib.sha1(repr(cam).encode()).hexdigest()[:10])
        out.append((png, dur, p))
        prev = cam
    return out


def add_fades(shots, fade, build: Path):
    """Dissolve between two different still images over `fade` seconds, taken from the start of the
    second; skipped around short shots (animation frames, scenes, camera moves)."""
    if fade <= 0:
        return shots
    from PIL import Image
    d = build / "fade"
    d.mkdir(exist_ok=True)
    n = max(1, round(fade * FPS))
    out = []
    for i, (png, dur, p) in enumerate(shots):
        if i and png != shots[i - 1][0] and dur >= 2 * fade and shots[i - 1][1] >= 2 * fade:
            a = shots[i - 1][0]
            key = hashlib.sha1(f"{a}|{png}|{n}".encode()).hexdigest()[:12]
            if not (d / f"{key}-{n}.png").exists():
                ia, ib = Image.open(a).convert("RGB"), Image.open(png).convert("RGB")
                for k in range(1, n + 1):
                    Image.blend(ia, ib, k / (n + 1)).save(d / f"{key}-{k}.png", compress_level=1)
            out += [(d / f"{key}-{k}.png", 1 / FPS, None) for k in range(1, n + 1)]
            dur -= n / FPS
        out.append((png, dur, p))
    return out


# ----------------------------------------------------------------------- tts
def pct(rate: str) -> int:
    """'+8%' -> 8, '-10%' -> -10."""
    m = re.fullmatch(r"([+-]?\d+)%?", rate.strip())
    if not m or not -50 <= int(m.group(1)) <= 100:
        sys.exit(f"bad --rate {rate!r}; use e.g. +8% or -5%")
    return int(m.group(1))


def load_lexicon(paths, lang="en"):
    """TSV 'written<TAB>spoken' respellings, applied to TTS text only (whole words).

    Chinese has no spaces, so there a Chinese term matches anywhere, and a Latin term wherever
    it is not part of a longer Latin word."""
    rules = []
    for path in paths:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#") and "\t" in line:
                    a, b = line.split("\t", 1)
                    w = re.escape(a.strip())
                    if lang != "zh":
                        rx = rf"\b{w}\b"
                    else:
                        rx = w if HAN.search(a) else rf"(?<![A-Za-z0-9]){w}(?![A-Za-z0-9])"
                    rules.append((re.compile(rx), b.strip()))

    def apply(text):
        for r, b in rules:
            text = r.sub(b, text)
        return text
    return apply


def engine_version(backend, lang="en"):
    """Part of the cache key: changing the TTS package or model invalidates old audio."""
    from importlib.metadata import version, PackageNotFoundError
    try:
        if backend == "edge":
            return "edge-tts " + version("edge-tts")
        if backend == "kokoro" and lang == "zh":
            return (f"kokoro-onnx {version('kokoro-onnx')} misaki {version('misaki-fork')} "
                    f"{(CACHE / 'kokoro-zh' / KOKORO_ZH[0]).stat().st_size}")
        if backend == "kokoro":
            return "kokoro-onnx " + version("kokoro-onnx") + f" {(CACHE / 'kokoro/kokoro-v1.0.int8.onnx').stat().st_size}"
    except (PackageNotFoundError, OSError):
        pass
    if backend == "chatterbox":
        return "chatterbox-mlx " + hashlib.sha1((SKILL / "scripts/chatterbox_worker.py").read_bytes()).hexdigest()[:8]
    return platform.mac_ver()[0] if backend == "say" else backend


def tts_key(backend, voice, rate, text, lang="en"):
    return hashlib.sha1(f"v3|{engine_version(backend, lang)}|{voice}|{rate}|{text}".encode()).hexdigest()[:16]


def words_file(wav: Path) -> Path:
    """Edge's word timings for a Chinese line: [[start s, end s, text], ...], beside its WAV."""
    return wav.with_suffix(".words.json")


def read_words(wav: Path):
    """The word timings of a cached line, or None when missing or damaged (then re-synthesized)."""
    try:
        marks = json.loads(words_file(wav).read_text(encoding="utf-8"))
        return marks if isinstance(marks, list) else None
    except (OSError, ValueError):
        return None


def to_wav(src: Path, dst: Path):
    """Convert to 24 kHz mono s16 WAV; write-then-rename so the cache never holds a partial file."""
    part = dst.with_name(dst.stem + ".part.wav")
    run([FF, "-y", "-loglevel", "error", "-i", src, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", part])
    if wav_seconds(part) <= 0:
        part.unlink()
        raise RuntimeError(f"empty audio for {dst.name}")
    os.replace(part, dst)


async def edge_with_words(text, voice, rate, mp3: Path, dst: Path):
    """Chinese: also keep Edge's word timings, so subtitles follow the speech exactly."""
    import edge_tts
    try:
        com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:  # edge-tts before `boundary`: word events come by default
        com = edge_tts.Communicate(text, voice, rate=rate)
    marks = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                marks.append([ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]])
    part = words_file(dst).with_suffix(".part")  # write-then-rename, like the WAVs
    part.write_text(json.dumps(marks, ensure_ascii=False), encoding="utf-8")
    os.replace(part, words_file(dst))


async def tts_edge(jobs, voice, rate, words=False):
    import edge_tts
    sem = asyncio.Semaphore(6)

    async def one(text, dst):
        async with sem:
            tmp = dst.with_suffix(".mp3")
            for attempt in range(3):
                limit = EDGE_LIMIT + len(text) / 10
                try:
                    job = (edge_with_words(text, voice, rate, tmp, dst) if words
                           else edge_tts.Communicate(text, voice, rate=rate).save(str(tmp)))
                    await asyncio.wait_for(job, limit)
                    to_wav(tmp, dst)
                    tmp.unlink()
                    return
                except asyncio.TimeoutError:
                    err = RuntimeError(f"no reply from the Edge voice service within {limit:.0f} s")
                except Exception as e:  # noqa: BLE001 - network hiccups: retry, then fall back
                    err = e
                    await asyncio.sleep(1 + attempt)
            raise err
    await asyncio.gather(*(one(t, d) for t, d in jobs))


def espeak_data():
    """Path of espeak-ng's data folder, short enough for espeak to accept.

    espeak-ng keeps the data path in a 160-byte buffer and silently falls back to the path
    baked in at build time when it is longer ("Error processing file .../phontab"), which
    happens when the cache sits in a deep folder. Then use a one-time copy (~20 MB) elsewhere."""
    import shutil, espeakng_loader
    src = Path(espeakng_loader.get_data_path()).resolve()
    if len(str(src)) < 120:
        return str(src)
    for d in (CACHE / "espeak-ng-data", Path(tempfile.gettempdir()) / "lecture-video-espeak-ng-data"):
        d = d.resolve()
        if len(str(d)) < 120:
            if not (d / "phontab").exists():
                part = d.with_name(d.name + ".part")
                shutil.rmtree(part, ignore_errors=True)
                shutil.copytree(src, part)
                os.replace(part, d)
            return str(d)
    sys.exit("the cache path is too long for the offline voice: set LECTURE_VIDEO_CACHE to a shorter folder")


def kokoro():
    from kokoro_onnx import Kokoro, EspeakConfig  # espeak-ng comes bundled (espeakng-loader)
    m = CACHE / "kokoro"
    return Kokoro(str(m / "kokoro-v1.0.int8.onnx"), str(m / "voices-v1.0.bin"),
                  espeak_config=EspeakConfig(data_path=espeak_data()))


def kokoro_selftest():
    """Called by setup: synthesize one sentence, so a broken offline voice shows up there."""
    a, sr = kokoro().create("Setup check.", voice=DEFAULT_VOICE["kokoro"], speed=1.0, lang="en-gb")
    assert len(a) / sr > 0.3, "Kokoro produced no audio"


def tts_kokoro(jobs, voice, rate):
    import soundfile as sf
    k = kokoro()
    speed = 1 + pct(rate) / 100
    for text, dst in jobs:
        a, sr = k.create(text, voice=voice, speed=speed, lang="en-gb")
        tmp = dst.with_suffix(".k.wav")
        sf.write(str(tmp), a, sr)
        to_wav(tmp, dst)
        tmp.unlink()


def kokoro_zh_ready() -> bool:
    """`lv.py setup --zh` installed the offline Chinese voice."""
    from importlib.util import find_spec
    return find_spec("misaki") is not None and all((CACHE / "kokoro-zh" / f).exists() for f in KOKORO_ZH)


def kokoro_zh():
    """Kokoro v1.1-zh with misaki's Chinese front end. English words inside the Chinese (c prime,
    alpha) go through espeak-ng; without that, misaki drops them silently."""
    import logging, warnings
    if not kokoro_zh_ready():
        sys.exit(f"the offline Chinese voice is not installed: run  python3 \"{SKILL / 'scripts/lv.py'}\" setup --zh")
    warnings.filterwarnings("ignore", category=SyntaxWarning)  # jieba's regexes on Python 3.12
    import jieba
    jieba.setLogLevel(logging.WARNING)
    from misaki import espeak, zh
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    EspeakWrapper.set_data_path(espeak_data())  # after misaki's import, which sets the bundled path
    import numpy as np
    from kokoro_onnx import Kokoro

    class KokoroZh(Kokoro):
        def _create_audio(self, phonemes, voice, speed):
            """kokoro-onnx 0.4 sends an input_ids export's speed as int32; this model wants a float
            (and an int would turn 1.1 into 1). Phonemes beyond the model's 509 are halved at a
            space and joined, never cut."""
            if len(phonemes) > 509:
                cut = phonemes.rfind(" ", 0, len(phonemes) // 2 + 1)
                cut = cut if cut > 0 else len(phonemes) // 2
                parts = [self._create_audio(p, voice, speed)[0] for p in (phonemes[:cut], phonemes[cut:])]
                return np.concatenate(parts), SR
            tokens = self.tokenizer.tokenize(phonemes)
            feed = {"input_ids": [[0, *tokens, 0]], "style": np.asarray(voice[len(tokens)], dtype=np.float32),
                    "speed": np.array([speed], dtype=np.float32)}
            return self.sess.run(None, feed)[0], SR
    en = espeak.EspeakG2P(language="en-us")
    g2p = zh.ZHG2P(version="1.1", en_callable=lambda word: en(word)[0])
    m = CACHE / "kokoro-zh"
    return KokoroZh(str(m / KOKORO_ZH[0]), str(m / KOKORO_ZH[1]), vocab_config=str(m / KOKORO_ZH[2])), g2p


def kokoro_zh_selftest():
    """Called by `setup --zh`: one Chinese sentence with English maths words in it."""
    k, g2p = kokoro_zh()
    a, sr = k.create(g2p("安装检查：c prime 等于 alpha。")[0], voice=ZH_VOICE["kokoro"], speed=1.0, is_phonemes=True)
    assert len(a) / sr > 0.8, "Kokoro (Chinese) produced no audio"


def tts_kokoro_zh(jobs, voice, rate):
    import soundfile as sf
    k, g2p = kokoro_zh()
    speed = 1 + pct(rate) / 100
    for text, dst in jobs:
        a, sr = k.create(g2p(text)[0], voice=voice, speed=speed, is_phonemes=True)
        tmp = dst.with_suffix(".k.wav")
        sf.write(str(tmp), a, sr)
        to_wav(tmp, dst)
        tmp.unlink()


def say_locale(voice):
    """macOS `say` voice -> its locale (zh_CN, en_GB, ...), '' if unknown or not on macOS."""
    if sys.platform != "darwin":
        return ""
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        m = re.match(r"(.+?)\s+([a-z]{2,3}_[A-Za-z0-9]+)\s+#", line)
        if m and m.group(1).strip() == voice:
            return m.group(2)
    return ""


def tts_say(jobs, voice, rate):
    if sys.platform != "darwin":
        sys.exit("--tts say exists only on macOS; use edge or kokoro")
    wpm = int(175 * (1 + pct(rate) / 100))
    for text, dst in jobs:
        tmp = dst.with_suffix(".aiff")
        run(["say", "-v", voice, "-r", str(wpm), "-o", tmp, text])
        to_wav(tmp, dst)
        tmp.unlink()


def tts_chatterbox(jobs, prof, rate):
    py = load_env().get("clone_python")
    if not py or not Path(py).exists():
        sys.exit(f"voice cloning is not installed: run  python3 \"{SKILL / 'scripts/lv.py'}\" setup --clone")
    raw = [(t, d.with_name(d.stem + ".cb.wav")) for t, d in jobs]
    spec = {"reference": str(prof["dir"] / prof["reference"]), "exaggeration": prof.get("exaggeration", 0.5),
            "cfg_weight": prof.get("cfg_weight", 0.5), "jobs": [{"text": t, "out": str(o)} for t, o in raw]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(spec, f)
    print(f"chatterbox: {len(jobs)} lines (slow: several minutes per minute of narration the first time)", flush=True)
    run([py, SKILL / "scripts/chatterbox_worker.py", f.name])
    os.unlink(f.name)
    tempo = 1 + pct(rate) / 100
    for (t, o), (_, d) in zip(raw, jobs):
        if tempo == 1:
            to_wav(o, d)
        else:  # Chatterbox has no speed control: time-stretch, pitch unchanged
            tmp = d.with_name(d.stem + ".at.wav")
            run([FF, "-y", "-loglevel", "error", "-i", o, "-af", f"atempo={tempo}", tmp])
            to_wav(tmp, d)
            tmp.unlink()
        o.unlink()


def synthesize(texts, backend, voice, rate, prof=None, lang="en"):
    """texts -> cached wav paths. Unchanged lines are never re-synthesized."""
    tdir = CACHE / "tts"
    tdir.mkdir(parents=True, exist_ok=True)
    paths = [tdir / f"{tts_key(backend, voice, rate, t, lang)}.wav" for t in texts]
    timed = lang == "zh" and backend == "edge"  # Chinese subtitles use Edge's word timings
    todo = [(t, p) for t, p in dict(zip(texts, paths)).items()
            if not valid_wav(p) or (timed and read_words(p) is None)]
    print(f"tts: {len(texts)} lines, {len(todo)} new ({backend}:{voice})", flush=True)
    if todo:
        try:
            {"edge": lambda: asyncio.run(tts_edge(todo, voice, rate, words=timed)),
             "kokoro": lambda: (tts_kokoro_zh if lang == "zh" else tts_kokoro)(todo, voice, rate),
             "say": lambda: tts_say(todo, voice, rate),
             "chatterbox": lambda: tts_chatterbox(todo, prof, rate)}[backend]()
        except Exception as e:  # noqa: BLE001
            if backend == "edge" and lang == "zh":  # offline -> the offline Chinese voice, if installed
                if not kokoro_zh_ready():
                    sys.exit(f"edge-tts failed ({e}). Chinese narration needs internet, or the offline Chinese "
                             f"voice: python3 \"{SKILL / 'scripts/lv.py'}\" setup --zh")
                print(f"edge-tts failed ({e}); falling back to kokoro {ZH_VOICE['kokoro']}")
                return synthesize(texts, "kokoro", ZH_VOICE["kokoro"], rate, lang=lang)
            if backend == "edge":  # offline / service hiccup -> local British female voice
                print(f"edge-tts failed ({e}); falling back to kokoro {DEFAULT_VOICE['kokoro']}")
                return synthesize(texts, "kokoro", DEFAULT_VOICE["kokoro"], rate)
            raise
    return paths


def valid_wav(p: Path) -> bool:
    """Cached audio is reused only if it parses as a non-empty WAV."""
    try:
        return p.exists() and wav_seconds(p) > 0.05
    except (wave.Error, EOFError, OSError):
        return False


def wav_seconds(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def write_track(parts, out: Path):
    """Concatenate 24 kHz mono s16 WAVs and silences (floats, in seconds) into one WAV."""
    with wave.open(str(out), "wb") as o:
        o.setnchannels(1)
        o.setsampwidth(2)
        o.setframerate(SR)
        for p in parts:
            if isinstance(p, float):
                o.writeframes(b"\0\0" * int(round(p * SR)))
            else:
                with wave.open(str(p)) as w:
                    o.writeframes(w.readframes(w.getnframes()))
    return wav_seconds(out)


# ------------------------------------------------------------------ subtitles
# Built from the narration text already in the .tex and timed from the synthesized audio,
# so they cost no tokens and no speech recognition, and stay in sync after every edit.
SUB_LANG = {"en": "eng", "de": "deu", "fr": "fra", "es": "spa", "it": "ita", "pt": "por", "nl": "nld",
            "zh": "zho", "ja": "jpn", "ko": "kor", "ru": "rus", "ar": "ara", "hi": "hin"}


def cue_chunks(text, max_chars=84):
    """Split one narration line into subtitle-sized pieces: sentences, then clauses, then words."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.replace("~", " ").strip()):
        while len(sent) > max_chars:
            cut = max(sent.rfind(p, 0, max_chars) for p in (", ", "; ", ": ", " - "))
            cut = cut + 1 if cut > max_chars // 3 else sent.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            out.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if sent:
            out.append(sent)
    return out


def wrap2(s, width=42):
    """At most two lines, broken at the space nearest the middle."""
    if len(s) <= width:
        return s
    mid = len(s) // 2
    left, right = s.rfind(" ", 0, mid + 1), s.find(" ", mid)
    cut = left if right < 0 or (left >= 0 and mid - left <= right - mid) else right
    return s[:cut] + "\n" + s[cut + 1:] if cut > 0 else s


def subtitle_cues(spoken):
    """[(start s, speech s, text, wav)] -> [(start, end, text)]; time shared by character count."""
    cues = []
    for start, dur, text, _ in spoken:
        chunks = cue_chunks(text)
        total = sum(len(c) for c in chunks) or 1
        t = start
        for c in chunks:
            d = dur * len(c) / total
            cues.append((t, t + d, wrap2(c)))
            t += d
    return cues


# Chinese, after Netflix's Simplified Chinese guide: at most 16 characters a line and two lines,
# commas and full stops shown as spaces. Lines break only between words (Edge's word marks, or
# jieba), never inside an English word or a number, and inside an English phrase only if needed.
ZH_LINE = 16
ZH_SENTENCE = re.compile(r"(?<=[。！？；!?;])")
ZH_CLAUSE = re.compile(r"(?<=[，、：,:])")
ZH_UNIT = re.compile(r"[A-Za-z0-9][\w.'′″%+\-]*|\s+|.", re.ASCII)
ZH_SOFT = "：、？！"  # a line may end after these


def zh_syllables(s):
    """Spoken length: 1 per Chinese character, ~1.7 per English word, ~1.3 per digit, 3 per %."""
    return (len(HAN.findall(s)) + 1.7 * len(re.findall(r"[A-Za-z]+", s))
            + 1.3 * len(re.findall(r"\d", s)) + 3 * s.count("%"))


def zh_width(s):
    """Full-width characters count 1, half-width ones (Latin, digits, spaces) 1/2."""
    return sum(1 if ord(c) >= 0x2E80 else 0.5 for c in s)


def zh_display(s):
    """Commas and full stops become one space, held as \\x1f (a clause break, unlike the spaces
    around English words) until the cue is written; nothing trails at the end but ？ or ！."""
    s = re.sub(r"[ \t\n]+", " ", s.replace("~", " "))
    s = re.sub("\x1f+", "\x1f", re.sub(r" ?(?:[，。；]|,(?= )|;) ?", "\x1f", s))
    return s.strip(" \x1f、：,:")


def zh_norm(t):
    """The spoken characters of t, as Edge's word marks hold them: letters, digits, Chinese."""
    return [c for c in t.lower() if c.isalnum()]


def zh_words(text, wav):
    """(start of each spoken character, character counts at which a word ends) for one line.
    From Edge's word marks, carried over to the written text when a lexicon respelling changed
    what was spoken; else no times, and word ends from jieba (installed with the offline voice)."""
    marks = read_words(wav) if wav else None
    if marks:
        chars, times, ends = [], [], set()
        for s, _, w in marks:
            for c in zh_norm(w):
                chars.append(c)
                times.append(s)
            ends.add(len(chars))
        orig = zh_norm(text)
        if chars == orig:
            return times, ends
        blocks = difflib.SequenceMatcher(None, orig, chars, autojunk=False).get_matching_blocks()
        if sum(b.size for b in blocks) >= 0.8 * len(orig):
            otimes, oends = [None] * len(orig), set()
            for a, b, n in blocks:
                for k in range(n):
                    otimes[a + k] = times[b + k]
                    if b + k + 1 in ends:
                        oends.add(a + k + 1)
            last = 0.0
            for i, t in enumerate(otimes):  # respelled characters take the time before them
                last = otimes[i] = last if t is None else t
            return otimes, oends
    try:
        import logging, warnings
        warnings.filterwarnings("ignore", category=SyntaxWarning)
        import jieba
        jieba.setLogLevel(logging.WARNING)
    except ImportError:
        return None, None
    ends, n = set(), 0
    for w in jieba.cut(text):
        n += len(zh_norm(w))
        ends.add(n)
    return None, ends


def zh_wrap(s, ends=None, off=0, width=ZH_LINE):
    """(s on one or two lines, whether that is a good fit, whether it broke at a comma or colon,
    True for one line). Two lines break where both fit, between words, inside an English phrase
    only if nothing else fits, preferably after a former comma or a colon unless that leaves a
    stub, and with the top line not longer. off = spoken characters before s in its line."""
    w = zh_width(s)
    if w <= width:
        return s, True, True
    units, pos, best = ZH_UNIT.findall(s), 0, None
    latin = lambda u: u[:1].isascii() and u[:1].isalnum()  # noqa: E731
    for i in range(1, len(units)):
        pos += len(units[i - 1])
        top, bot = s[:pos].rstrip(), s[pos:].lstrip()
        if not top or not bot:
            continue
        natural = "\x1f" in (units[i], units[i - 1]) or units[i - 1] in ZH_SOFT
        word_ok = natural or ends is None or off + len(zh_norm(top)) in ends
        before = units[i - 2] if units[i - 1].isspace() and i >= 2 else units[i - 1]
        after = units[i + 1] if units[i].isspace() and i + 1 < len(units) else units[i]
        tw, bw = zh_width(top), zh_width(bot)
        key = (max(tw, bw) > width or not word_ok, not word_ok, latin(before) and latin(after),
               not (natural and min(tw, bw) >= w / 4), tw - bw > 1, abs(tw - bw))
        if best is None or key < best[0]:
            best = (key, top + "\n" + bot, natural)
    return (best[1], not best[0][0], best[2]) if best else (s, False, False)


def zh_split(s, ends, off):
    """A clause that cannot make a good cue -> near-equal pieces, cut between words."""
    n = max(2, math.ceil(zh_width(zh_display(s)) / (2 * ZH_LINE)))
    target = zh_width(zh_display(s)) / n
    out, cur = [], ""
    for u in ZH_UNIT.findall(s):
        if (zh_display(cur) and len(out) < n - 1 and zh_width(zh_display(cur + u)) > target
                and (ends is None or off + len(zh_norm(cur)) in ends)):
            out.append(cur)
            off += len(zh_norm(cur))
            cur = ""
        cur += u
    return out + [cur]


def zh_chunks(text, ends=None):
    """One narration line -> [(cue text, spoken characters before it)]: clauses packed while the
    cue still breaks well into at most two lines (between clauses, once it holds more than one).
    A sentence end closes the cue unless the cue is a stub (好！), which joins the next one."""
    out, cur, cur_off = [], "", 0

    def good(t, o, packed=False):
        _, fits, natural = zh_wrap(zh_display(t), ends, o)
        return bool(zh_display(t)) and fits and (natural or not packed)

    def pieces(s, o):  # split until every piece makes a good cue, or cannot be split further
        if good(s, o):
            return [s]
        parts, out_ = zh_split(s, ends, o), []
        if len(parts) < 2:
            return parts
        for p in parts:
            out_ += pieces(p, o)
            o += len(zh_norm(p))
        return out_

    def flush():
        nonlocal cur, cur_off
        if zh_display(cur):
            out.append((cur, cur_off))
        cur_off += len(zh_norm(cur))
        cur = ""
    for sent in ZH_SENTENCE.split(text.strip()):
        for clause in ZH_CLAUSE.split(sent):
            if not zh_display(cur + clause) or good(cur + clause, cur_off, bool(zh_display(cur))):
                cur += clause
                continue
            flush()
            *done, cur = pieces(clause, cur_off)
            for p in done:
                out.append((p, cur_off))
                cur_off += len(zh_norm(p))
        if zh_width(zh_display(cur)) >= 6:
            flush()
    flush()
    return out


def zh_subtitle_cues(spoken):
    """[(start s, speech s, text, wav)] -> [(start, end, text)], in order and never overlapping."""
    cues = []
    for start, dur, text, wav in spoken:
        times, ends = zh_words(text, wav)
        chunks = zh_chunks(text, ends) or [(text, 0)]
        if times:
            starts = [times[min(o, len(times) - 1)] for _, o in chunks]
        else:  # share the time by spoken length
            w = [zh_syllables(c) or 1 for c, _ in chunks]
            starts = [dur * sum(w[:k]) / sum(w) for k in range(len(chunks))]
        starts[0], prev = 0.0, 0.0
        for k, (c, o) in enumerate(chunks):
            a = max(starts[k], prev)
            b = max(starts[k + 1] if k + 1 < len(chunks) else dur, a + 0.3)  # at least 0.3 s on screen
            cues.append((start + a, start + b, zh_wrap(zh_display(c), ends, o)[0].replace("\x1f", " ")))
            prev = b
    for k in range(len(cues) - 1):  # a long last cue must not run into the next line's first
        if cues[k][1] > cues[k + 1][0]:
            cues[k] = (cues[k][0], cues[k + 1][0], cues[k][2])
    return cues


def write_subtitles(cues, out: Path):
    """out.srt (players, YouTube) and out.vtt (web pages)."""
    def ts(t, sep):
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"
    srt, vtt = out.with_suffix(".srt"), out.with_suffix(".vtt")
    srt.write_text("".join(f"{i}\n{ts(a, ',')} --> {ts(b, ',')}\n{txt}\n\n" for i, (a, b, txt) in enumerate(cues, 1)),
                   encoding="utf-8")
    vtt.write_text("WEBVTT\n\n" + "".join(f"{ts(a, '.')} --> {ts(b, '.')}\n{txt}\n\n" for a, b, txt in cues),
                   encoding="utf-8")
    return srt, vtt


# ------------------------------------------------------------------- assemble
def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("tex")
    ap.add_argument("out", nargs="?", help="output .mp4 (default: <output_dir or work folder>/<folder name>.mp4)")
    ap.add_argument("--tts", choices=["edge", "kokoro", "say", "chatterbox"])
    ap.add_argument("--voice", help="engine voice id, or a voice profile name")
    ap.add_argument("--rate", help=f"speech rate, e.g. +10%% (default: profile rate, else {DEFAULT_RATE.replace('%', '%%')})")
    ap.add_argument("--height", type=int, default=cfg.get("height"),
                    help="video height (default 720; 1080 when the lecture has animated scenes)")
    ap.add_argument("--pad", type=float, default=0.4, help="silence after each narrated line (s)")
    ap.add_argument("--fade", type=float, default=cfg.get("fade", 0.25),
                    help="seconds of dissolve when a slide changes (0: hard cuts)")
    ap.add_argument("--lexicon", help="extra written<TAB>spoken respellings (WORK/lexicon.tsv is read too)")
    ap.add_argument("--no-subs", action="store_true", help="skip subtitles (default: .srt + .vtt beside the "
                    "MP4 and a selectable subtitle track inside it)")
    ap.add_argument("--sheet", action="store_true", help="also write contact sheets")
    ap.add_argument("--sheet-only", action="store_true")
    a = ap.parse_args()
    tex = Path(a.tex).expanduser().resolve()
    if not tex.exists():
        sys.exit(f"no such file: {tex}")
    work = tex.parent
    zh = lecture_lang(tex) == "zh"
    if not zh and HAN.search(tex_source(tex)):
        sys.exit("this lecture contains Chinese text but is set up as English. For a Chinese lecture, load "
                 "\\usepackage[zh]{lecturevideo} (references/chinese.md); otherwise remove the Chinese text.")
    vcfg = (cfg.get("zh") or {}) if zh else cfg  # top-level voice settings are for English lectures
    a.voice = a.voice or (None if a.tts else vcfg.get("voice"))
    a.tts = a.tts or vcfg.get("tts") or "edge"
    a.rate = a.rate or vcfg.get("rate")
    prof = find_profile(a.voice, work) if a.voice else None
    if prof:
        a.tts = prof["engine"]
        a.rate = a.rate or prof.get("rate")
        voice = prof.get("voice") or "ref-" + hashlib.sha1((prof["dir"] / prof["reference"]).read_bytes()).hexdigest()[:12] \
            + f"-e{prof.get('exaggeration', 0.5)}-c{prof.get('cfg_weight', 0.5)}"
        print(f"voice profile: {prof['label']} ({a.tts})")
    elif a.tts == "chatterbox":
        sys.exit("--tts chatterbox needs --voice <profile> with a reference recording")
    else:
        voice = a.voice or (ZH_VOICE if zh else DEFAULT_VOICE)[a.tts]
    if zh and not ((a.tts == "edge" and voice.lower().startswith("zh-"))
                   or (a.tts == "kokoro" and voice[:3] in ("zf_", "zm_"))
                   or (a.tts == "say" and say_locale(voice).startswith("zh"))):
        sys.exit(f"{prof['label'] if prof else voice} ({a.tts}) cannot narrate Chinese. Use a Chinese voice: "
                 f"Edge zh-CN-... / zh-TW-... (default {ZH_VOICE['edge']}) or, offline, Kokoro zf_... / zm_... "
                 "(references/chinese.md). "
                 "Cloned voices speak English only.")
    a.rate = a.rate or (ZH_RATE if zh else DEFAULT_RATE)
    if zh:
        print(f"language: Chinese (XeLaTeX, {a.tts}:{voice}, Chinese subtitles)")
    status = brand_status(work)
    print("branding: " + ("none yet (lv.py brand adds a logo and a name)" if status == "ask" else status))

    build = work / f"{tex.stem}_build"
    build.mkdir(exist_ok=True)
    # Elaborated lectures: check each animated scene and refresh its stills before LaTeX shows them.
    scenes = {}  # name -> each beat's own length (ms)
    for name, k in re.findall(r"\\lvscene\s*\{([^}]*)\}\s*\{\s*(\d+)\s*\}", tex_source(tex)):
        import scene as sc
        scenes[name] = sc.prepare(work / "scenes" / f"{name}.html", sheet=a.sheet or a.sheet_only)
        if len(scenes[name]) != int(k):
            sys.exit(f"scenes/{name}.html has {len(scenes[name])} beats (LV.beat calls) but the lecture says "
                     f"\\lvscene{{{name}}}{{{k}}}: make them match, one \\say per beat")
        if a.sheet or a.sheet_only:
            print(f"scene sheet: {work / 'scenes' / (name + '-sheet.png')}")
    a.height = a.height or (1080 if scenes else 720)
    log = compile_tex(tex, (prof or {}).get("credit", ""), "xelatex" if zh else "pdf")
    pdf = tex.with_suffix(".pdf")
    pngs = rasterize(pdf, build, a.height)
    n = len(pngs)
    pages, meta = read_narr(tex, n, "zh" if zh else "en")
    missing = [i + 1 for i, p in enumerate(pages) if p is None]
    if missing:
        sys.exit(f"pages without \\say or \\wait: {missing}  (every overlay page needs one)")
    if zh and not any(p[0] == "say" and HAN.search(p[1]) for p in pages):
        sys.exit("this lecture is set up as Chinese ([zh]) but its narration has no Chinese. Write the \\say "
                 "text in Chinese, or drop the zh option for an English lecture.")
    if a.sheet or a.sheet_only:
        for s in contact_sheets(pngs, build):
            print("sheet:", s)
    for w in layout_warnings(log)[:12]:
        print("layout:", w)
    # one span per \say event: an animation's pages share the event id of its single \say
    spans = []  # (kind, value, [page indices], event id)
    for i, p in enumerate(pages):
        if p[0] == "say" and spans and spans[-1][0] == "say" and spans[-1][3] == p[2] and spans[-1][2][-1] == i - 1:
            spans[-1][2].append(i)
        else:
            spans.append([p[0], p[1], [i], p[2]])
    words = sum(len(s[1].split()) for s in spans if s[0] == "say")
    waits = sum(s[1] for s in spans if s[0] == "wait")
    nsay = sum(s[0] == "say" for s in spans)
    if zh:  # Chinese has no spaces: count spoken syllables instead of words
        said = [s[1] for s in spans if s[0] == "say"]
        syl, spm = sum(map(zh_syllables, said)), ZH_SPM * (1 + pct(a.rate) / 100)
        print(f"{n} pages, {sum(len(HAN.findall(x)) for x in said)} Chinese characters + "
              f"{sum(len(re.findall(r'[A-Za-z]+', x)) for x in said)} English words = ~{syl:.0f} spoken syllables "
              f"in {nsay} lines + {waits:.0f}s pauses (~{syl / spm + waits / 60 + nsay * a.pad / 60:.1f} min "
              f"at ~{spm:.0f} syllables/min)")
    else:
        print(f"{n} pages, {words} narrated words in {nsay} lines + {waits:.0f}s pauses "
              f"(~{words / 165 + waits / 60 + nsay * a.pad / 60:.1f} min at ~165 wpm)")
    if a.sheet_only:
        return

    out = Path(a.out).expanduser() if a.out else \
        Path(cfg.get("output_dir") or work).expanduser() / f"{work.name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    speak = load_lexicon([SKILL / "assets/lexicon.tsv", CONFIG / "lexicon.tsv", work / "lexicon.tsv"]
                         + ([Path(a.lexicon).expanduser()] if a.lexicon else []), "zh" if zh else "en")
    texts = [speak(s[1]) for s in spans if s[0] == "say"]
    if zh and a.tts == "kokoro" and not kokoro_zh_ready():  # asked for the offline Chinese voice: install it once
        print("installing the offline Chinese voice (one time, ~270 MB)", flush=True)
        run([sys.executable, SKILL / "scripts/lv.py", "setup", "--zh"])
        importlib.invalidate_caches()
    wavs = iter(synthesize(texts, a.tts, voice, a.rate, prof, "zh" if zh else "en"))

    vlist, alist = [], []  # (png, seconds, page) and [wav path | silence seconds]
    spoken, t = [], 0.0    # (start, speech seconds, display text, wav) for subtitles; t = track time
    beats = {}             # scene name -> {beat: seconds}
    for kind, val, idx, _ in spans:
        if kind == "wait":
            dur = float(val)
            alist.append(dur)
        else:
            w = next(wavs)
            speech = wav_seconds(w)
            spoken.append((t, speech, val, w))  # subtitles show the text as written, not lexicon respellings
            dur = speech + a.pad
            alist += [w, float(a.pad)]
        sc_beat = meta["scene"].get(idx[0])
        if sc_beat:  # a scene beat lasts its sentence, or its own motion if that is longer
            name, b = sc_beat
            if len(idx) > 1 or b in beats.get(name, {}):
                sys.exit(f"scene {name}: give each beat its own \\say<k> (page {idx[0] + 1})")
            need = scenes[name][b - 1] / 1000 + 0.3
            if need > dur:
                alist.append(need - dur)
                dur = need
            beats.setdefault(name, {})[b] = dur
            vlist.append(("scene", name, b, dur))
        elif kind == "wait" or len(idx) == 1:
            vlist.append((pngs[idx[0]], dur, idx[0]))
        else:  # animation: motion fills ~80% of its sentence (2-24 fps), then holds
            step = max(1 / 24, 0.8 * dur / (len(idx) - 1))
            anim = step * (len(idx) - 1)
            if anim > dur:  # narration shorter than animation: stretch audio with silence
                alist.append(anim - dur + 0.3)
                dur = anim + 0.3
            for j in idx[:-1]:
                vlist.append((pngs[j], step, j))
            vlist.append((pngs[idx[-1]], dur - anim, idx[-1]))
        t += dur

    # scenes: render each one's frames for the beat lengths just settled, then splice them in
    frames = {}
    for name, got in beats.items():
        if sorted(got) != list(range(1, len(scenes[name]) + 1)):
            sys.exit(f"scene {name}: beats {sorted(got)} are narrated, but it has {len(scenes[name])}")
        lens = [got[b] for b in sorted(got)]
        frames[name] = sc.render_frames(work / "scenes" / f"{name}.html", lens, FPS, a.height, build / "scenes" / name)
    shots = []
    for v in vlist:
        if v[0] == "scene":
            _, name, b, dur = v
            fr = frames[name][b - 1]
            shots += [(f, 1 / FPS, None) for f in fr[:-1]] + [(fr[-1], dur - (len(fr) - 1) / FPS, None)]
        else:
            shots.append(v)
    shots = add_fades(apply_camera(shots, meta["cam"], meta["frame"], pdf, build), a.fade, build)
    vlist = [(p, d) for p, d, _ in shots]

    def q(p):  # ffmpeg concat quoting: ' -> '\''
        p = Path(p).as_posix()
        if "\n" in p:
            sys.exit(f"newline in path: {p!r}")
        return "file '" + p.replace("'", "'\\''") + "'\n"
    (build / "video.txt").write_text("".join(f"{q(p)}duration {d:.3f}\n" for p, d in vlist) + q(vlist[-1][0]),
                                     encoding="utf-8")  # ffmpeg reads UTF-8 paths, whatever the OS locale
    total = write_track(alist, build / "track.wav")
    subs, sub_args = None, []
    if not a.no_subs:
        subs = write_subtitles((zh_subtitle_cues if zh else subtitle_cues)(spoken), out)
        lang = "zho" if zh else "eng" if a.tts != "edge" else SUB_LANG.get(voice[:2].lower(), "und")
        sub_args = ["-i", subs[0], "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:s", "mov_text",
                    "-metadata:s:s:0", f"language={lang}"]
    quality = ["-crf", "23"] if scenes else ["-tune", "stillimage", "-crf", "28"]  # scenes are full motion
    run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", build / "video.txt",
         "-i", build / "track.wav", *sub_args, "-vf", "fps=24,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", *quality,
         "-c:a", "aac", "-b:a", "64k", "-t", f"{total:.3f}", "-movflags", "+faststart", out])
    # -t, not -shortest: with a sparse subtitle stream, -shortest can wait forever
    for ext in ("aux", "fls", "fdb_latexmk", "log", "nav", "out", "snm", "toc", "vrb", "xdv"):
        f = work / f"{tex.stem}.{ext}"
        if f.exists():
            f.unlink()
    print(f"wrote {out}  {total / 60:.1f} min  {out.stat().st_size / 1e6:.1f} MB")
    if subs:
        print(f"subtitles: {subs[0].name} + {subs[1].name} beside the video, and a selectable track inside it")


if __name__ == "__main__":
    main()
