#!/usr/bin/env python3
"""Prepare lecture notes for reading. Run this before planning any video.

For each page it decides whether the text layer is usable. Pages with too little
extractable text (handwriting, scans, photos of a whiteboard) are rendered to
grayscale JPEGs sized for vision reading, so the agent can look at them itself.

usage (through lv.py): lv.py ingest NOTES [NOTES ...] --out WORKDIR [--visual 3,7-9]
                                   [--min-words 40] [--width 1400]
NOTES may be .pdf, images (.png .jpg .jpeg .heic .webp .tif), .md, .txt or .tex.
Writes: WORKDIR/source.txt (text-layer pages), WORKDIR/pages/*.jpg (pages that must be
read visually), WORKDIR/glance-*.jpg (colour contact sheets of ALL PDF pages, 6 per sheet, so
margin annotations and unlabeled diagrams on typed pages are not missed) and
WORKDIR/manifest.tsv (file, page, words, mode). Image pages cost roughly 1-2k tokens each,
a glance sheet about the same for six pages: read each once and transcribe.
"""
import argparse, re, sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvcommon import HAN  # noqa: E402

try:  # iPhone photos
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

IMAGES = {".png", ".jpg", ".jpeg", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}


def render(page, width, gray):
    img = page.render(scale=width / page.get_width()).to_pil()
    return img.convert("L" if gray else "RGB")


def glance_sheets(thumbs, out: Path):
    """3x2 colour contact sheets of every PDF page, in order."""
    cw, ch, sheets = 600, 776, []
    for k in range(0, len(thumbs), 6):
        sheet = Image.new("RGB", (3 * cw, 2 * ch), "white")
        for i, t in enumerate(thumbs[k:k + 6]):
            t = ImageOps.contain(t, (cw, ch))
            sheet.paste(t, ((i % 3) * cw + (cw - t.width) // 2, (i // 3) * ch + (ch - t.height) // 2))
        path = out / f"glance-{k // 6 + 1}.jpg"
        sheet.save(path, quality=70)
        sheets.append(path)
    return sheets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notes", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-words", type=int, default=40)
    ap.add_argument("--width", type=int, default=1400)
    ap.add_argument("--visual", default="", help="extra PDF pages to read at full size, e.g. 3,7-9 "
                    "(use after a glance sheet shows handwriting or annotations on a typed page)")
    a = ap.parse_args()
    force = set()
    for part in filter(None, a.visual.split(",")):
        lo, _, hi = part.partition("-")
        force.update(range(int(lo), int(hi or lo) + 1))
    srcs = [Path(p).expanduser() for p in a.notes]
    for src in srcs:  # validate everything before touching an earlier run's output
        if not src.exists():
            sys.exit(f"not found: {src}  (if the OS blocks access, ask the user to move the file or grant access)")
        if src.suffix.lower() not in IMAGES | {".pdf", ".md", ".txt", ".tex"}:
            sys.exit(f"unsupported: {src}  (convert .docx/.pptx/.key to PDF first)")
    out = Path(a.out).expanduser()
    (out / "pages").mkdir(parents=True, exist_ok=True)
    for old in list((out / "pages").glob("*.jpg")) + list(out.glob("glance-*.jpg")):
        old.unlink()  # a re-run must not leave pages from an earlier input set
    text_parts, visual, thumbs, manifest = [], [], [], ["file\tpage\twords\tmode"]

    for idx, src in enumerate(srcs, 1):
        tag = f"{idx:02d}-{re.sub(r'[^A-Za-z0-9]+', '_', src.stem)[:40]}"  # unique per input
        ext = src.suffix.lower()
        if ext in {".md", ".txt", ".tex"}:
            text_parts.append(f"===== {src.name} =====\n{src.read_text(encoding='utf-8', errors='replace')}")
            manifest.append(f"{src.name}\t-\t-\ttext")
        elif ext == ".pdf":
            doc = pdfium.PdfDocument(str(src))
            for p in range(1, len(doc) + 1):
                page = doc[p - 1]
                t = page.get_textpage().get_text_range()
                # a Chinese word is ~2 characters; Chinese has no spaces to count by
                words = len(re.findall(r"[A-Za-z]{2,}", t)) + len(HAN.findall(t)) // 2
                # figures carry little text even in typed notes: render those pages too
                has_figure = bool(re.search(r"\b(Fig(ure)?\.?\s*\d+|Diagram|Table)\b|[图表]\s*\d", t))
                if words >= a.min_words:
                    text_parts.append(f"===== {src.name} p{p} =====\n{t}")
                mode = "visual" if words < a.min_words else "text+figure" if has_figure else "text"
                manifest.append(f"{src.name}\t{p}\t{words}\t{mode}")
                thumbs.append(render(page, 600, gray=False))
                if words < a.min_words or has_figure or p in force:
                    dst = out / "pages" / f"{tag}-p{p:03d}.jpg"
                    render(page, a.width, gray=True).save(dst, quality=70)
                    why = ("handwritten/scanned" if words < a.min_words else
                           "requested" if p in force else "has figure")
                    visual.append((dst, why))
        elif ext in IMAGES:
            dst = out / "pages" / f"{tag}.jpg"
            try:
                im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
            except Exception as e:  # noqa: BLE001
                sys.exit(f"cannot open image {src}: {e}")
            im.thumbnail((a.width, a.width))
            im.save(dst, quality=80)
            manifest.append(f"{src.name}\t1\t0\tvisual")
            visual.append((dst, "image"))

    (out / "source.txt").write_text("\n\n".join(text_parts), encoding="utf-8")
    (out / "manifest.tsv").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    sheets = glance_sheets(thumbs, out)
    words = sum(len(t.split()) for t in text_parts)
    han = sum(len(HAN.findall(t)) for t in text_parts)
    latin = sum(len(re.findall(r"[A-Za-z]{2,}", t)) for t in text_parts)
    if han + latin < 20:
        print("language: unknown (little or no text layer): decide from the pages you read")
    else:
        print(f"language: {'zh (Chinese)' if han > latin else 'en (English)'}  "
              f"({han} Chinese characters, {latin} English words)")
    size = f"{han} Chinese characters + {latin} English words" if han > latin else f"{words} words"
    print(f"text layer: {size} -> {out / 'source.txt'}")
    print(f"read visually ({len(visual)} pages):")
    for p, why in visual:
        print(f"  {p}   [{why}]")
    if sheets:
        print(f"glance at every page ({len(sheets)} sheets, 6 pages each, in order):")
        for s in sheets:
            print(f"  {s}")
    print("Next: look at every glance sheet. If one shows handwriting, annotations or a figure you "
          "need on a typed page, re-run with --visual PAGES. Read every [handwritten/scanned], [image] and "
          f"[requested] page at full size, transcribe into {out / 'transcript.md'}, then plan from "
          "source.txt + transcript.md only.")


if __name__ == "__main__":
    main()
