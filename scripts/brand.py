#!/usr/bin/env python3
"""Brand the slides with the user's logo and name. `lv.py brand` runs this in the skill's venv.

  lv.py brand --logo FILE --name "Name" [--name-zh 中文名] [--blackletter] [--keep-background] [--work DIR]
  lv.py brand --none [--work DIR]      no branding; remembered, so the agent stops asking
  lv.py brand [--work DIR]             show what the next lecture gets

The brand file is the built-in theme plus \\lvlogo and \\lvname: the logo at the left of every frame
title, and on the title page with the name beside it. It goes to CONFIG/tex (every lecture) or, with
--work, into one work folder, which then wins. Each run test-builds the template with it and saves a
preview of the title page and one slide. A brand file this command did not write (or that was edited
since) is never overwritten.
"""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvcommon import (BRAND_JSON, BRAND_STY, CACHE, CONFIG, HAN, SKILL, brand_record, brand_status,  # noqa: E402
                      compile_latex, latex_errors, load_config, load_env, save_config)

LOGO = "lecturevideo-logo"  # + .png or .pdf, beside the brand file
RASTER = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"}
TEX_SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
               "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
GOTHIC = (r"\RequirePackage{yfonts}\DeclareFontShape{LYG}{ygoth}{m}{n}{<->ygoth}{}"  # scalable, for 20 pt
          r"\renewcommand{\lvnamefont}{\gothfamily}")


def tex_escape(s):
    return "".join(TEX_SPECIAL.get(c, c) for c in s)


def near_white(px):
    return min(px[:3]) >= 235


def svg_reader():
    """svglib (pure Python, ~10 MB with reportlab and lxml), installed into the venv on first use."""
    try:
        from svglib.svglib import svg2rlg
        return svg2rlg
    except ImportError:
        pass
    uv = load_env().get("uv")
    if uv:
        print("logo: installing an SVG converter into the skill's Python (svglib, ~10 MB, once)", flush=True)
        e = dict(os.environ, UV_CACHE_DIR=str(CACHE / "uv-cache"))
        subprocess.run([uv, "pip", "install", "-q", "--python", sys.executable, "svglib>=1.5"], env=e)
        shutil.rmtree(CACHE / "uv-cache", ignore_errors=True)
    try:
        from svglib.svglib import svg2rlg
        return svg2rlg
    except ImportError:
        sys.exit("cannot convert an SVG logo here (svglib did not install): save it as PNG or PDF and run "
                 "lv.py brand again")


def prepare_logo(src: Path, d: Path, keep_background: bool) -> str:
    """Copy the logo into d as PNG or PDF (LaTeX reads both); return its file name."""
    ext = src.suffix.lower()
    if ext == ".pdf":
        if src.read_bytes()[:5] != b"%PDF-":
            sys.exit(f"{src} is not a PDF file")
        shutil.copy(src, d / f"{LOGO}.pdf")
        return f"{LOGO}.pdf"
    if ext == ".svg":
        out = d / f"{LOGO}.pdf"
        for cmd in (["rsvg-convert", "-f", "pdf", "-o", str(out), str(src)],
                    ["inkscape", str(src), "--export-type=pdf", f"--export-filename={out}"]):
            if shutil.which(cmd[0]) and subprocess.run(cmd, capture_output=True).returncode == 0 and out.exists():
                return out.name
        svg2rlg = svg_reader()
        drawing = svg2rlg(str(src))
        if drawing is None:
            sys.exit(f"cannot read {src.name} as SVG: save the logo as PNG or PDF and run lv.py brand again")
        from reportlab.graphics import renderPDF
        renderPDF.drawToFile(drawing, str(out))
        return out.name
    if ext not in RASTER:
        sys.exit(f"{src.name}: use a PNG, JPG, PDF or SVG logo")
    from PIL import Image, ImageDraw
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    im = Image.open(src).convert("RGBA")
    im.thumbnail((1200, 1200))  # sharp at slide size, quick to compile
    w, h = im.size
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    # A logo saved on plain white shows as a white box on the ivory slides: clear the white that
    # touches the border, leaving white inside the emblem alone.
    if (not keep_background and im.getchannel("A").getextrema()[0] == 255
            and sum(near_white(im.getpixel(c)) for c in corners) >= 3):
        import numpy as np
        mark = (1, 254, 3)
        filled = im.convert("RGB")
        for c in corners:
            if near_white(filled.getpixel(c)):
                ImageDraw.floodfill(filled, c, mark, thresh=60)
        px = np.asarray(im).copy()
        px[(np.asarray(filled) == mark).all(-1), 3] = 0
        im = Image.fromarray(px, "RGBA")
        print("logo: made its white background transparent so it sits on the slide colour "
              "(--keep-background keeps it)")
    box = im.getchannel("A").getbbox()  # trim empty margins: they would push the name away
    if box and box != (0, 0, w, h):
        im = im.crop(box)
    im.save(d / f"{LOGO}.png")
    return f"{LOGO}.png"


def brand_tex(logo, name, name_zh, blackletter):
    """The brand file: built-in theme, logo, and the name per language (Chinese lectures use
    name_zh when given). Blackletter only for names without Chinese characters."""
    def name_lines(n):
        if not n:
            return []
        return ([GOTHIC] if blackletter and not HAN.search(n) else []) + [rf"\lvname{{{tex_escape(n)}}}"]
    en, zh = name_lines(name), name_lines(name_zh or name)
    lines = [f"% {BRAND_STY} -- written by `lv.py brand` on {datetime.date.today()}; run it again to change.",
             "% Built-in theme plus a logo and a name. Once edited by hand, `lv.py brand` leaves it alone.",
             r"\ProvidesPackage{lecturevideo-brand}",
             r"\usetheme{lecturevideo}",
             r"\providecommand{\lvname}[1]{}\providecommand{\lvnamefont}{}% older lecturevideo.sty: logo only"]
    if logo:
        lines.append(rf"\lvlogo{{{logo}}}")
    if en == zh:
        lines += en
    else:
        lines += [r"\iflv@zh", *zh, r"\else", *en, r"\fi"]
    return "\n".join(lines + [r"\endinput", ""])


def save_brand(d: Path, tex: str, rec: dict):
    (d / BRAND_STY).write_text(tex, encoding="utf-8")
    rec["sha1"] = hashlib.sha1(tex.encode("utf-8")).hexdigest()
    (d / BRAND_JSON).write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clear(d: Path):
    """Remove a brand written by this command (never a hand-written one: callers check first)."""
    for f in [d / BRAND_STY, d / BRAND_JSON, *d.glob(LOGO + ".*")]:
        f.unlink(missing_ok=True)


def build(stage: Path, zh: bool):
    """Compile the template with the staged brand: (title page, first slide) images, or the error."""
    with tempfile.TemporaryDirectory() as t:
        tex = Path(t) / "lecture.tex"
        shutil.copy(SKILL / "assets" / ("template-zh.tex" if zh else "template.tex"), tex)
        good, log = compile_latex(tex, extra_inputs=[stage], engine="xelatex" if zh else "pdf")
        if not good:
            return None, latex_errors(log)
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(tex.with_suffix(".pdf")))
        return [doc[i].render(scale=640 / doc[i].get_width()).to_pil().convert("RGB") for i in (0, 1)], ""


def main():
    ap = argparse.ArgumentParser(prog="lv.py brand", description=__doc__.split("\n\n")[0])
    ap.add_argument("--logo", type=Path, help="PNG, JPG, PDF or SVG")
    ap.add_argument("--name", help="shown beside the logo on the title page (institution, course, channel...)")
    ap.add_argument("--name-zh", help="the name for Chinese lectures, if different")
    ap.add_argument("--blackletter", action="store_true", help="Gothic letters for the name (Latin script only)")
    ap.add_argument("--keep-background", action="store_true", help="keep a raster logo's white background")
    ap.add_argument("--none", action="store_true", help="no logo or name (remembered)")
    ap.add_argument("--work", type=Path, help="brand only the lecture in this work folder")
    a = ap.parse_args()
    d = (a.work.expanduser().resolve() if a.work else CONFIG / "tex")
    if not (a.logo or a.name or a.name_zh or a.none):
        print(f"branding: {brand_status(a.work)}")
        return
    if a.none and (a.logo or a.name or a.name_zh):
        sys.exit("--none cannot be combined with a logo or a name")
    if (d / BRAND_STY).exists() and brand_record(d) is None:
        sys.exit(f"{d / BRAND_STY} was not written by lv.py brand (or was edited since), so it is left alone. "
                 "Rename or move it, then run lv.py brand again.")
    d.mkdir(parents=True, exist_ok=True)
    cfg = load_config()

    if a.none:
        clear(d)
        if a.work:  # this lecture only: the built-in theme, whatever is saved for the others
            save_brand(d, "% written by `lv.py brand --none`: no logo or name for this lecture\n"
                          "\\ProvidesPackage{lecturevideo-brand}\n\\usetheme{lecturevideo}\n\\endinput\n",
                       {"none": True})
        else:
            cfg["branding"] = "none"
            save_config(cfg)
        print(f"branding: {brand_status(a.work)}")
        return

    name, name_zh = (a.name or "").strip(), (a.name_zh or "").strip() or None
    if any("\n" in n for n in (name, name_zh or "")):
        sys.exit("the name must be one line")
    if HAN.search(name):
        if name_zh:
            sys.exit("--name is for English lectures, which cannot show Chinese characters: put the Chinese "
                     "name in --name-zh and an English one (or none) in --name")
        name, name_zh = "", name
        print("note: English lectures cannot show Chinese characters, so they get the logo without a name "
              "(add --name for an English one); Chinese lectures show the name")
    if a.logo and not a.logo.expanduser().is_file():
        sys.exit(f"logo not found: {a.logo}")
    for n in (name, name_zh or ""):
        if len(n) > 60:
            print(f"note: a long name wraps onto two lines on the title page: {n}")

    with tempfile.TemporaryDirectory() as t:
        stage = Path(t)
        logo = prepare_logo(a.logo.expanduser().resolve(), stage, a.keep_background) if a.logo else ""
        tex = brand_tex(logo, name, name_zh, a.blackletter)
        rec = {"name": name, "name_zh": name_zh, "logo": logo, "source": str(a.logo or ""),
               "blackletter": a.blackletter}
        save_brand(stage, tex, rec)
        shots, err = build(stage, zh=False)
        if shots is None:
            sys.exit(f"the slides do not build with this logo or name, so nothing was changed:\n{err}")
        if load_env().get("tex_zh_ok") or name_zh:  # Chinese lectures in use here: test them too
            zh_shots, err = build(stage, zh=True)
            if zh_shots is None:
                print(f"WARNING: Chinese lectures do not build with this branding (English ones do):\n{err}")
            else:
                shots.append(zh_shots[0])
        clear(d)
        for f in stage.iterdir():
            shutil.copy(f, d / f.name)
    if not a.work and cfg.get("branding") == "none":
        del cfg["branding"]
        save_config(cfg)

    from PIL import Image
    w, h = shots[0].size
    sheet = Image.new("RGB", (w * len(shots) + 8 * (len(shots) - 1), h), "white")
    for i, im in enumerate(shots):
        sheet.paste(im, (i * (w + 8), 0))
    preview = (d if a.work else CONFIG) / "brand-preview.png"
    sheet.save(preview)
    print(f"branding: {brand_status(a.work)}")
    print(f"preview: {preview}  (title page, a slide{', the Chinese title page' if len(shots) > 2 else ''})")


if __name__ == "__main__":
    main()
