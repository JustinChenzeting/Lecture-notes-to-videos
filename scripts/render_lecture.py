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
import argparse, asyncio, hashlib, json, math, os, platform, re, subprocess, sys, tempfile, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvcommon import CACHE, CONFIG, SKILL, compile_latex, ffmpeg, latex_errors, load_config, load_env  # noqa: E402

SR = 24000
DEFAULT_RATE = "+10%"
DEFAULT_VOICE = {"edge": "en-GB-SoniaNeural", "kokoro": "bf_emma", "say": "Shelley (English (UK))"}
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
def compile_tex(tex: Path, credit=""):
    pre = [f"-usepretex=\\def\\lvvoicecredit{{{credit}}}"] if credit else []
    stamp = tex.parent / f"{tex.stem}_build" / "credit.txt"  # latexmk can't see a pretex change
    force = ["-g"] if not stamp.exists() or stamp.read_text() != credit else []
    stamp.write_text(credit)
    good, log = compile_latex(tex, [*force, *pre])
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


def read_narr(tex: Path, npages: int):
    """Return per-page (kind, value, event_id) with kind 'say' | 'wait', or None.

    Each record is page|kind|frame|ordinal|overlay-spec|text. The event id is
    (frame, ordinal, spec, text); only range specs (<2-13>) may span several pages."""
    pages = [None] * npages
    narr = (tex.parent / f"{tex.stem}.narr").read_text(encoding="utf-8", errors="replace")
    for n, line in enumerate(narr.splitlines(), 1):
        try:
            p, kind, frame, ordn, spec, val = line.split("|", 5)
            p = int(p) - 1
            assert 0 <= p < npages and kind in ("say", "wait")
        except (ValueError, AssertionError):
            sys.exit(f".narr line {n} malformed: {line[:80]}")
        val = " ".join(val.replace("\\ ", " ").split())
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
    return pages


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


# ----------------------------------------------------------------------- tts
def pct(rate: str) -> int:
    """'+8%' -> 8, '-10%' -> -10."""
    m = re.fullmatch(r"([+-]?\d+)%?", rate.strip())
    if not m or not -50 <= int(m.group(1)) <= 100:
        sys.exit(f"bad --rate {rate!r}; use e.g. +8% or -5%")
    return int(m.group(1))


def load_lexicon(paths):
    """TSV 'written<TAB>spoken' respellings, applied to TTS text only (whole words)."""
    rules = []
    for path in paths:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#") and "\t" in line:
                    a, b = line.split("\t", 1)
                    rules.append((re.compile(rf"\b{re.escape(a.strip())}\b"), b.strip()))

    def apply(text):
        for r, b in rules:
            text = r.sub(b, text)
        return text
    return apply


def engine_version(backend):
    """Part of the cache key: changing the TTS package or model invalidates old audio."""
    from importlib.metadata import version, PackageNotFoundError
    try:
        if backend == "edge":
            return "edge-tts " + version("edge-tts")
        if backend == "kokoro":
            return "kokoro-onnx " + version("kokoro-onnx") + f" {(CACHE / 'kokoro/kokoro-v1.0.int8.onnx').stat().st_size}"
    except (PackageNotFoundError, OSError):
        pass
    if backend == "chatterbox":
        return "chatterbox-mlx " + hashlib.sha1((SKILL / "scripts/chatterbox_worker.py").read_bytes()).hexdigest()[:8]
    return platform.mac_ver()[0] if backend == "say" else backend


def tts_key(backend, voice, rate, text):
    return hashlib.sha1(f"v3|{engine_version(backend)}|{voice}|{rate}|{text}".encode()).hexdigest()[:16]


def to_wav(src: Path, dst: Path):
    """Convert to 24 kHz mono s16 WAV; write-then-rename so the cache never holds a partial file."""
    part = dst.with_name(dst.stem + ".part.wav")
    run([FF, "-y", "-loglevel", "error", "-i", src, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", part])
    if wav_seconds(part) <= 0:
        part.unlink()
        raise RuntimeError(f"empty audio for {dst.name}")
    os.replace(part, dst)


async def tts_edge(jobs, voice, rate):
    import edge_tts
    sem = asyncio.Semaphore(6)

    async def one(text, dst):
        async with sem:
            tmp = dst.with_suffix(".mp3")
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, voice, rate=rate).save(str(tmp))
                    to_wav(tmp, dst)
                    tmp.unlink()
                    return
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


def synthesize(texts, backend, voice, rate, prof=None):
    """texts -> cached wav paths. Unchanged lines are never re-synthesized."""
    tdir = CACHE / "tts"
    tdir.mkdir(parents=True, exist_ok=True)
    paths = [tdir / f"{tts_key(backend, voice, rate, t)}.wav" for t in texts]
    todo = [(t, p) for t, p in dict(zip(texts, paths)).items() if not valid_wav(p)]
    print(f"tts: {len(texts)} lines, {len(todo)} new ({backend}:{voice})", flush=True)
    if todo:
        try:
            {"edge": lambda: asyncio.run(tts_edge(todo, voice, rate)),
             "kokoro": lambda: tts_kokoro(todo, voice, rate),
             "say": lambda: tts_say(todo, voice, rate),
             "chatterbox": lambda: tts_chatterbox(todo, prof, rate)}[backend]()
        except Exception as e:  # noqa: BLE001
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
    """[(start s, speech s, text)] -> [(start, end, text)]; time shared by character count."""
    cues = []
    for start, dur, text in spoken:
        chunks = cue_chunks(text)
        total = sum(len(c) for c in chunks) or 1
        t = start
        for c in chunks:
            d = dur * len(c) / total
            cues.append((t, t + d, wrap2(c)))
            t += d
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
    ap.add_argument("--height", type=int, default=cfg.get("height", 720))
    ap.add_argument("--pad", type=float, default=0.4, help="silence after each narrated line (s)")
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
    a.voice = a.voice or (None if a.tts else cfg.get("voice"))
    a.tts = a.tts or cfg.get("tts") or "edge"
    a.rate = a.rate or cfg.get("rate")
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
        voice = a.voice or DEFAULT_VOICE[a.tts]
    a.rate = a.rate or DEFAULT_RATE

    build = work / f"{tex.stem}_build"
    build.mkdir(exist_ok=True)
    log = compile_tex(tex, (prof or {}).get("credit", ""))
    pdf = tex.with_suffix(".pdf")
    pngs = rasterize(pdf, build, a.height)
    n = len(pngs)
    pages = read_narr(tex, n)
    missing = [i + 1 for i, p in enumerate(pages) if p is None]
    if missing:
        sys.exit(f"pages without \\say or \\wait: {missing}  (every overlay page needs one)")
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
    print(f"{n} pages, {words} narrated words in {nsay} lines + {waits:.0f}s pauses "
          f"(~{words / 165 + waits / 60 + nsay * a.pad / 60:.1f} min at ~165 wpm)")
    if a.sheet_only:
        return

    out = Path(a.out).expanduser() if a.out else \
        Path(cfg.get("output_dir") or work).expanduser() / f"{work.name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    speak = load_lexicon([SKILL / "assets/lexicon.tsv", CONFIG / "lexicon.tsv", work / "lexicon.tsv"]
                         + ([Path(a.lexicon).expanduser()] if a.lexicon else []))
    texts = [speak(s[1]) for s in spans if s[0] == "say"]
    wavs = iter(synthesize(texts, a.tts, voice, a.rate, prof))

    vlist, alist = [], []  # (png, seconds) and [wav path | silence seconds]
    spoken, t = [], 0.0    # (start, speech seconds, display text) for subtitles; t = track time
    for kind, val, idx, _ in spans:
        if kind == "wait":
            vlist.append((pngs[idx[0]], val))
            alist.append(float(val))
            t += val
            continue
        w = next(wavs)
        speech = wav_seconds(w)
        spoken.append((t, speech, val))  # subtitles show the text as written, not lexicon respellings
        dur = speech + a.pad
        alist += [w, float(a.pad)]
        if len(idx) == 1:
            vlist.append((pngs[idx[0]], dur))
        else:  # animation: motion fills ~80% of its sentence (2-12 fps), then holds
            step = max(1 / 12, 0.8 * dur / (len(idx) - 1))
            anim = step * (len(idx) - 1)
            if anim > dur:  # narration shorter than animation: stretch audio with silence
                alist.append(anim - dur + 0.3)
                dur = anim + 0.3
            for j in idx[:-1]:
                vlist.append((pngs[j], step))
            vlist.append((pngs[idx[-1]], dur - anim))
        t += dur

    def q(p):  # ffmpeg concat quoting: ' -> '\''
        p = Path(p).as_posix()
        if "\n" in p:
            sys.exit(f"newline in path: {p!r}")
        return "file '" + p.replace("'", "'\\''") + "'\n"
    (build / "video.txt").write_text("".join(f"{q(p)}duration {d:.3f}\n" for p, d in vlist) + q(vlist[-1][0]))
    total = write_track(alist, build / "track.wav")
    subs, sub_args = None, []
    if not a.no_subs:
        subs = write_subtitles(subtitle_cues(spoken), out)
        lang = "eng" if a.tts != "edge" else SUB_LANG.get(voice[:2].lower(), "und")
        sub_args = ["-i", subs[0], "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:s", "mov_text",
                    "-metadata:s:s:0", f"language={lang}"]
    run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", build / "video.txt",
         "-i", build / "track.wav", *sub_args, "-vf", "fps=24,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
         "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "28",
         "-c:a", "aac", "-b:a", "64k", "-t", f"{total:.3f}", "-movflags", "+faststart", out])
    # -t, not -shortest: with a sparse subtitle stream, -shortest can wait forever
    for ext in ("aux", "fls", "fdb_latexmk", "log", "nav", "out", "snm", "toc", "vrb"):
        f = work / f"{tex.stem}.{ext}"
        if f.exists():
            f.unlink()
    print(f"wrote {out}  {total / 60:.1f} min  {out.stat().st_size / 1e6:.1f} MB")
    if subs:
        print(f"subtitles: {subs[0].name} + {subs[1].name} beside the video, and a selectable track inside it")


if __name__ == "__main__":
    main()
