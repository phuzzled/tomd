<div align="center">

# TOMD

### *Any document. Pure Markdown. One command.*

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Powered by Pandoc](https://img.shields.io/badge/Powered%20by-Pandoc-orange?style=flat-square)](https://pandoc.org)
[![PDF via PyMuPDF](https://img.shields.io/badge/PDF%20via-PyMuPDF4LLM-red?style=flat-square)](https://github.com/pymupdf/RAG)

</div>

---

You have a folder full of PDFs, EPUBs, DOCXs, and ancient RTFs.  
You need clean, readable Markdown.  
You don't want to think about it.

**That's TOMD.**

Drop it in a directory. Run `tomd`. Done.

---

## ✨ What It Does

TOMD is a blazing-fast, terminal-native document converter that turns virtually any document format into clean, LLM-ready Markdown — with a gorgeous live progress display, per-file status tracking, and page-by-page PDF progress reporting.

No GUIs. No configuration files. No nonsense.

---

## 📦 Supported Formats

| Format      | Extensions                          | Engine             |
|-------------|-------------------------------------|--------------------|
| **PDF**     | `.pdf`                              | PyMuPDF4LLM        |
| **Word**    | `.docx`                             | Pandoc             |
| **eBook**   | `.epub`                             | Pandoc             |
| **Kindle**  | `.mobi`, `.azw`, `.azw3`            | Calibre + Pandoc   |
| **Web**     | `.html`, `.htm`, `.xhtml`           | Pandoc             |
| **Slides**  | `.pptx`                             | Pandoc             |
| **Docs**    | `.odt`, `.rtf`, `.docbook`, `.fb2`  | Pandoc             |
| **Code**    | `.rst`, `.tex`, `.org`, `.ipynb`    | Pandoc             |
| **Data**    | `.csv`, `.tsv`, `.json`             | Pandoc             |
| **Wiki**    | `.mediawiki`, `.wiki`, `.opml`      | Pandoc             |

---

## 🚀 Installation

**The recommended way** — install globally with [`pipx`](https://pipx.pypa.io/) so it's available everywhere on your system:

```bash
# Install pipx if you don't have it
brew install pipx && pipx ensurepath

# Clone the repo
git clone https://github.com/phuzzled/tomd.git
cd tomd

# Install globally (editable — code changes take effect immediately)
pipx install -e .
```

You can now run `tomd` from any directory on your machine.

> **Prerequisites:** Install [Pandoc](https://pandoc.org/installing.html) for most formats. For Kindle files, install [Calibre](https://calibre-ebook.com/download).
> ```bash
> brew install pandoc
> brew install --cask calibre
> ```

---

## 🎯 Usage

```bash
# Convert all supported files in the current directory
tomd

# Convert specific files
tomd report.pdf brief.docx chapter.epub

# Recurse into subdirectories
tomd -r

# Force overwrite of existing .md files
tomd --force

# Write output to a specific directory
tomd --output-dir ./converted

# Combine options
tomd -r --force --output-dir ./markdown

# Show version
tomd -v
```

All converted files land in a `md-done/` folder (or wherever you point `--output-dir`), leaving your originals exactly where they are.

---

## 🖥️ What You'll See

TOMD uses a sleek, live-updating terminal display powered by **Rich**:

- **Live results table** — every file ticks ✓ green, ⊘ yellow (skipped), or ✗ red (failed) as it completes
- **File progress bar** — tracks how many files have been processed
- **PDF page bar** — for large PDFs, a `█░░░░░░░░░` bar shows page-by-page progress so you're never left wondering
- **Final summary** — a clean table of every result when the run is complete

No blinking cursors. No silent freezes. Just pure, observable progress.

---

## 🤖 Built for LLMs

TOMD's PDF engine is powered by **PyMuPDF4LLM**, specifically designed to produce structured, clean Markdown that preserves:

- Headings, bold, italic, tables  
- Reading order across multi-column layouts  
- Inline code and technical notation

Feed the output directly into your RAG pipelines, vector databases, or AI workflows. TOMD gets the docs in; your model does the rest.

---

## ⚙️ Options Reference

| Option              | Short | Description                                             |
|---------------------|-------|---------------------------------------------------------|
| `--force`           | `-f`  | Overwrite existing `.md` output files                   |
| `--recursive`       | `-r`  | Recurse into subdirectories                             |
| `--output-dir DIR`  | `-o`  | Write `.md` files to a specific directory               |
| `--quiet`           | `-q`  | Suppress the banner; show only results                  |
| `--version`         | `-v`  | Print current version and exit                          |
| `--help`            | `-h`  | Show help and exit                                      |

---

## 🛠️ Development

```bash
git clone https://github.com/phuzzled/tomd.git
cd tomd

# Install in editable mode (changes to the source reflect immediately)
pipx install -e .

# Or use a virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest
```

---

## 📄 License

MIT — free to use, modify, and distribute.

---

<div align="center">

**Stop copy-pasting. Start converting.**

</div>
