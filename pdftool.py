#!/usr/bin/env python3
"""
pdftool — PDF toolkit CLI for humans and AI agents.

A lightweight alternative to browser-based PDF tools.
Uses pypdf + pdfplumber + ocrmypdf + img2pdf + Pillow + ghostscript.

Usage:
    pdftool merge a.pdf b.pdf -o merged.pdf
    pdftool split input.pdf 1-5,10-15 -o out/
    pdftool compress input.pdf --quality screen
    pdftool ocr scanned.pdf
    pdftool rotate input.pdf 90
    pdftool watermark input.pdf "CONFIDENTIAL"
    pdftool convert input.docx              # office→pdf
    pdftool convert input.pdf --to images   # pdf→images
    pdftool convert *.jpg --to pdf -o album.pdf
    pdftool info document.pdf
    pdftool meta document.pdf --title "New Title" --author "Me"
    pdftool unlock secured.pdf              # remove password
    pdftool protect input.pdf --password "secret"
    pdftool blank input.pdf                 # remove blank pages
"""
import argparse
import io
import os
import sys
import tempfile
import subprocess
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────

def _output_path(input_path, suffix, out_dir=None):
    """Generate output path: same dir as input, with suffix, or custom dir."""
    p = Path(input_path)
    stem = p.stem
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        return str(out / f"{stem}{suffix}")
    return str(p.parent / f"{stem}{suffix}")


def _output_pdf(input_path, suffix="-out", out=None):
    """Return output .pdf path."""
    if out:
        return out
    return _output_path(input_path, f"{suffix}.pdf")


# ── Commands ─────────────────────────────────────────────────

def cmd_merge(files, output):
    """Merge multiple PDFs into one."""
    from pypdf import PdfWriter, PdfReader
    writer = PdfWriter()
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages:
            writer.add_page(page)
    with open(output, "wb") as f:
        writer.write(f)
    n = sum(len(PdfReader(f).pages) for f in files)
    print(f"Merged {len(files)} files ({n} pages) → {output}")


def cmd_split(input_pdf, ranges, out_dir=None):
    """Split PDF by page ranges. ranges="1-5,10-15" or "1,3,5"."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    total = len(reader.pages)
    p = Path(input_pdf)
    out_dir = out_dir or str(p.parent)
    os.makedirs(out_dir, exist_ok=True)

    for part_spec in ranges.split(","):
        part_spec = part_spec.strip()
        if "-" in part_spec:
            a, b = part_spec.split("-", 1)
            a = int(a.strip() or 1)
            b = int(b.strip() or total)
        else:
            a = b = int(part_spec)
        # 1-indexed → 0-indexed
        a = max(1, a) - 1
        b = min(total, b) - 1

        writer = PdfWriter()
        for i in range(a, b + 1):
            writer.add_page(reader.pages[i])
        outname = os.path.join(out_dir, f"{p.stem}_p{a+1}-{b+1}.pdf")
        with open(outname, "wb") as f:
            writer.write(f)
        print(f"  {a+1}-{b+1} → {outname}")


def cmd_extract(input_pdf, pages, output):
    """Extract specific pages. pages="1,3,5-8"."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    total = len(reader.pages)
    writer = PdfWriter()

    page_nums = []
    for part in pages.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a.strip() or 1)
            b = int(b.strip() or total)
            page_nums.extend(range(a, b + 1))
        else:
            page_nums.append(int(part))

    for n in page_nums:
        if 1 <= n <= total:
            writer.add_page(reader.pages[n - 1])

    with open(output, "wb") as f:
        writer.write(f)
    print(f"Extracted {len(writer.pages)} pages → {output}")


def cmd_compress(input_pdf, output=None, quality="ebook"):
    """Compress PDF via ghostscript."""
    output = _output_pdf(input_pdf, "-compressed", output)
    gs_quality = {
        "screen": "/screen",
        "ebook": "/ebook",
        "printer": "/printer",
        "prepress": "/prepress",
    }.get(quality, "/ebook")

    subprocess.run([
        "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={gs_quality}",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output}", input_pdf,
    ], check=True)

    orig = os.path.getsize(input_pdf)
    new = os.path.getsize(output)
    print(f"Compressed {orig/1024:.0f}K → {new/1024:.0f}K "
          f"({(1 - new/orig)*100:.0f}% reduction) → {output}")


def cmd_ocr(input_pdf, output=None, language="eng+chi_sim"):
    """OCR scanned PDF to searchable PDF."""
    import ocrmypdf
    output = _output_pdf(input_pdf, "-ocr", output)
    ocrmypdf.ocr(input_pdf, output, language=language, deskew=True)
    print(f"OCR complete → {output}")


def cmd_rotate(input_pdf, angle, pages=None, output=None):
    """Rotate pages. angle: 90, 180, 270."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    angle = int(angle)

    if pages:
        page_set = set()
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                page_set.update(range(int(a), int(b) + 1))
            else:
                page_set.add(int(part))

    for i, page in enumerate(reader.pages):
        if pages is None or (i + 1) in page_set:
            page.rotate(angle)
        writer.add_page(page)

    output = _output_pdf(input_pdf, f"-rot{angle}", output)
    with open(output, "wb") as f:
        writer.write(f)
    scope = f"pages {pages}" if pages else "all pages"
    print(f"Rotated {scope} by {angle}° → {output}")


def cmd_watermark(input_pdf, text, output=None, opacity=0.15, font_size=60):
    """Add diagonal text watermark to every page."""
    from pypdf import PdfReader, PdfWriter
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    output = _output_pdf(input_pdf, "-watermarked", output)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFillAlpha(opacity)
    c.setFont('Helvetica', font_size)
    c.translate(300, 400)
    c.rotate(45)
    tw = c.stringWidth(text, 'Helvetica', font_size)
    c.drawString(-tw/2, 0, text)
    c.save()
    buf.seek(0)

    wm = PdfReader(buf)
    for page in reader.pages:
        page.merge_page(wm.pages[0])
        writer.add_page(page)

    with open(output, "wb") as f:
        writer.write(f)
    print(f"Watermarked {len(reader.pages)} pages → {output}")


def cmd_images2pdf(images, output):
    """Convert images to single PDF using img2pdf."""
    import img2pdf
    if output is None:
        output = "output.pdf"
    with open(output, "wb") as f:
        f.write(img2pdf.convert(sorted(images)))
    print(f"{len(images)} images → {output}")


def cmd_pdf2images(input_pdf, out_dir=None, dpi=150, fmt="png"):
    """Convert PDF pages to images."""
    from PIL import Image
    import pypdfium2 as pdfium

    p = Path(input_pdf)
    out_dir = out_dir or str(p.parent / f"{p.stem}_images")
    os.makedirs(out_dir, exist_ok=True)

    pdf = pdfium.PdfDocument(input_pdf)
    n_pages = len(pdf)
    for i in range(n_pages):
        page = pdf[i]
        bitmap = page.render(scale=dpi / 72.0)
        pil_image = bitmap.to_pil()
        out_name = os.path.join(out_dir, f"{p.stem}_p{i+1:03d}.{fmt}")
        pil_image.save(out_name)
        print(f"  page {i+1}/{n_pages} → {out_name}")

    print(f"{n_pages} pages → {out_dir}/")


def cmd_office2pdf(input_file, output=None):
    """Convert Office document to PDF via LibreOffice headless."""
    out_dir = output or os.path.dirname(os.path.abspath(input_file)) or "."
    if os.path.isdir(out_dir):
        out_dir = os.path.abspath(out_dir)
    subprocess.run([
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", out_dir, input_file
    ], check=True, capture_output=True)
    p = Path(input_file)
    result = os.path.join(out_dir, f"{p.stem}.pdf")
    if os.path.exists(result):
        print(f"Converted → {result}")
    else:
        # LibreOffice is not installed, give a helpful message
        print("Error: libreoffice not installed. Run: sudo apt install libreoffice-core")
        sys.exit(1)


def cmd_info(input_pdf):
    """Show PDF metadata and page count."""
    from pypdf import PdfReader
    reader = PdfReader(input_pdf)
    meta = {}
    try:
        meta = reader.metadata or {}
    except Exception:
        pass
    print(f"File:     {input_pdf}")
    try:
        pages = len(reader.pages)
        print(f"Pages:    {pages}")
    except Exception:
        print(f"Pages:    (encrypted, cannot read)")
        print(f"Size:     {os.path.getsize(input_pdf)/1024:.0f} KB")
        return
    if meta.title:
        print(f"Title:    {meta.title}")
    if meta.author:
        print(f"Author:   {meta.author}")
    if meta.subject:
        print(f"Subject:  {meta.subject}")
    if meta.creator:
        print(f"Creator:  {meta.creator}")
    if meta.producer:
        print(f"Producer: {meta.producer}")
    # Page sizes
    if reader.pages:
        p0 = reader.pages[0]
        w = float(p0.mediabox.width)
        h = float(p0.mediabox.height)
        print(f"Size:     {w:.0f}×{h:.0f} pts ({w/72:.1f}×{h/72:.1f} in)")
    # Encryption
    if reader.is_encrypted:
        print(f"Encrypted: yes")
    print(f"Size:     {os.path.getsize(input_pdf)/1024:.0f} KB")


def cmd_meta(input_pdf, title=None, author=None, subject=None, output=None):
    """Edit PDF metadata."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    md = reader.metadata or {}
    if title:
        writer.add_metadata({"/Title": title})
    if author:
        mut = dict(md)
        mut["/Author"] = author
        writer.add_metadata(mut)
    if subject:
        mut = dict(md)
        mut["/Subject"] = subject
        writer.add_metadata(mut)

    output = _output_pdf(input_pdf, "-meta", output)
    with open(output, "wb") as f:
        writer.write(f)
    print(f"Metadata updated → {output}")


def cmd_unlock(input_pdf, password="", output=None):
    """Remove password protection."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    if reader.is_encrypted:
        reader.decrypt(password)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    output = _output_pdf(input_pdf, "-unlocked", output)
    with open(output, "wb") as f:
        writer.write(f)
    print(f"Password removed → {output}")


def cmd_protect(input_pdf, password, output=None):
    """Add password protection."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    output = _output_pdf(input_pdf, "-protected", output)
    with open(output, "wb") as f:
        writer.write(f)
    print(f"Encrypted → {output}")


def cmd_blank(input_pdf, output=None, threshold=0.01):
    """Remove blank/near-blank pages."""
    from pypdf import PdfReader, PdfWriter
    import pdfplumber

    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    removed = 0

    for i, page in enumerate(reader.pages):
        with pdfplumber.open(input_pdf) as pdf:
            p = pdf.pages[i]
            text = p.extract_text() or ""
            chars = len(text.strip())
            # Check for images
            has_images = bool(p.images)
            if chars < 5 and not has_images:
                removed += 1
                continue
        writer.add_page(page)

    output = _output_pdf(input_pdf, "-noblank", output)
    with open(output, "wb") as f:
        writer.write(f)
    print(f"Removed {removed} blank pages → {output} ({len(writer.pages)} pages)")


# ── Main CLI ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="pdftool — PDF toolkit CLI",
        usage="pdftool <command> [options]"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # merge
    p = sub.add_parser("merge", help="Merge PDFs")
    p.add_argument("files", nargs="+")
    p.add_argument("-o", "--output", default="merged.pdf")

    # split
    p = sub.add_parser("split", help="Split PDF by page ranges")
    p.add_argument("input")
    p.add_argument("ranges", help="e.g. '1-5,10-15' or '1,3,5'")
    p.add_argument("-o", "--out-dir")

    # extract
    p = sub.add_parser("extract", help="Extract pages")
    p.add_argument("input")
    p.add_argument("pages", help="e.g. '1,3,5-8'")
    p.add_argument("-o", "--output", default="extracted.pdf")

    # compress
    p = sub.add_parser("compress", help="Compress PDF")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("-q", "--quality", default="ebook",
                   choices=["screen", "ebook", "printer", "prepress"])

    # ocr
    p = sub.add_parser("ocr", help="OCR scanned PDF")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("-l", "--lang", default="eng+chi_sim")

    # rotate
    p = sub.add_parser("rotate", help="Rotate pages")
    p.add_argument("input")
    p.add_argument("angle", type=int, choices=[90, 180, 270])
    p.add_argument("-p", "--pages", help="Page range (default: all)")
    p.add_argument("-o", "--output")

    # watermark
    p = sub.add_parser("watermark", help="Add text watermark")
    p.add_argument("input")
    p.add_argument("text")
    p.add_argument("-o", "--output")
    p.add_argument("--opacity", type=float, default=0.1)
    p.add_argument("--font-size", type=int, default=60)

    # convert
    p = sub.add_parser("convert", help="Convert between formats")
    p.add_argument("input", nargs="+")
    p.add_argument("--to", choices=["pdf", "images"], required=True)
    p.add_argument("-o", "--output", help="Output file or directory")
    p.add_argument("--dpi", type=int, default=150)

    # info
    p = sub.add_parser("info", help="Show PDF info")

    p.add_argument("input")

    # meta
    p = sub.add_parser("meta", help="Edit PDF metadata")
    p.add_argument("input")
    p.add_argument("--title")
    p.add_argument("--author")
    p.add_argument("--subject")
    p.add_argument("-o", "--output")

    # unlock
    p = sub.add_parser("unlock", help="Remove password")
    p.add_argument("input")
    p.add_argument("-p", "--password", default="")
    p.add_argument("-o", "--output")

    # protect
    p = sub.add_parser("protect", help="Add password")
    p.add_argument("input")
    p.add_argument("--password", required=True)
    p.add_argument("-o", "--output")

    # blank
    p = sub.add_parser("blank", help="Remove blank pages")
    p.add_argument("input")
    p.add_argument("-o", "--output")

    args = parser.parse_args()

    # Route to command
    cmd = args.command
    if cmd == "merge":
        cmd_merge(args.files, args.output)
    elif cmd == "split":
        cmd_split(args.input, args.ranges, args.out_dir)
    elif cmd == "extract":
        cmd_extract(args.input, args.pages, args.output)
    elif cmd == "compress":
        cmd_compress(args.input, args.output, args.quality)
    elif cmd == "ocr":
        cmd_ocr(args.input, args.output, args.lang)
    elif cmd == "rotate":
        cmd_rotate(args.input, args.angle, args.pages, args.output)
    elif cmd == "watermark":
        cmd_watermark(args.input, args.text, args.output, args.opacity, args.font_size)
    elif cmd == "convert":
        if args.to == "pdf":
            # Auto-detect: images → pdf or office → pdf
            ext = os.path.splitext(args.input[0])[1].lower()
            if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"):
                cmd_images2pdf(args.input, args.output)
            else:
                cmd_office2pdf(args.input[0], args.output)
        elif args.to == "images":
            cmd_pdf2images(args.input[0], args.output, args.dpi)
    elif cmd == "info":
        cmd_info(args.input)
    elif cmd == "meta":
        cmd_meta(args.input, args.title, args.author, args.subject, args.output)
    elif cmd == "unlock":
        cmd_unlock(args.input, args.password, args.output)
    elif cmd == "protect":
        cmd_protect(args.input, args.password, args.output)
    elif cmd == "blank":
        cmd_blank(args.input, args.output)


if __name__ == "__main__":
    main()
