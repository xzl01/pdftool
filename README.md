# pdftool

PDF toolkit CLI — merge, split, compress, OCR, rotate, watermark, convert, and more.

A lightweight, pip-installable alternative to browser-based PDF tools. All processing is local — your documents never leave your machine.

## Install

```bash
pip install git+https://github.com/xzl01/pdftool.git
```

Or from source:

```bash
git clone https://github.com/xzl01/pdftool.git
cd pdftool
pip install .
```

**System dependencies:** `ghostscript` (for compression) and optionally `libreoffice-core` (for Office→PDF conversion).

```bash
sudo apt install ghostscript libreoffice-core tesseract-ocr tesseract-ocr-chi-sim
```

## Usage

```bash
# Merge
pdftool merge a.pdf b.pdf -o combined.pdf

# Split by page ranges
pdftool split input.pdf "1-5,10-15"

# Extract specific pages
pdftool extract input.pdf "2,4,6-8" -o out.pdf

# Compress (screen / ebook / printer / prepress)
pdftool compress large.pdf -q screen

# OCR scanned PDF (Chinese + English)
pdftool ocr scanned.pdf

# Rotate pages
pdftool rotate input.pdf 90
pdftool rotate input.pdf 180 -p "1,3,5"

# Watermark
pdftool watermark contract.pdf "CONFIDENTIAL"

# Convert between formats
pdftool convert document.docx --to pdf       # Office → PDF
pdftool convert input.pdf --to images        # PDF → images
pdftool convert *.jpg --to pdf -o album.pdf  # Images → PDF

# Metadata
pdftool info document.pdf
pdftool meta input.pdf --title "Report" --author "Alice"

# Security
pdftool protect input.pdf --password "s3cret"
pdftool unlock secured.pdf

# Remove blank pages
pdftool blank scanned.pdf
```

## Commands

| Command | Description |
|---------|-------------|
| `merge` | Combine multiple PDFs into one |
| `split` | Split by page ranges (e.g. "1-5,10-15") |
| `extract` | Extract specific pages |
| `compress` | Reduce file size via ghostscript |
| `ocr` | Make scanned PDFs searchable |
| `rotate` | Rotate pages (90°/180°/270°) |
| `watermark` | Add diagonal text watermark |
| `convert` | Office→PDF, PDF→images, images→PDF |
| `info` | Show page count, metadata, size |
| `meta` | Edit title / author / subject |
| `unlock` | Remove password protection |
| `protect` | Add password encryption |
| `blank` | Remove blank / near-blank pages |

## Dependencies

All pure Python, installed automatically:

- `pypdf` — core PDF operations
- `pdfplumber` — text extraction and blank detection
- `ocrmypdf` — OCR engine
- `img2pdf` — lossless image→PDF
- `pypdfium2` — PDF→image rendering
- `Pillow` — image handling
- `reportlab` — watermark rendering

## License

MIT
