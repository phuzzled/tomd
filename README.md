# TOMD — Universal Document → Markdown Converter

A cross-platform CLI tool that converts document files to Markdown. Navigate to any folder, type `tomd`, and every supported file gets converted.

## Supported Formats

| Format | Engine |
|---|---|
| **PDF** | [PyMuPDF4LLM](https://github.com/pymupdf/RAG) |
| **DOCX, EPUB, ODT, RTF, HTML, LaTeX, RST, Textile, MediaWiki, DocBook, FB2, OPML, Org, PPTX** | [Pandoc](https://pandoc.org) |
| **MOBI, AZW, AZW3** | [Calibre](https://calibre-ebook.com) → Pandoc |

## Installation

### Prerequisites

**Pandoc** is required for most formats (everything except PDF):

```bash
# macOS
brew install pandoc

# Ubuntu / Debian
sudo apt install pandoc

# Windows
choco install pandoc    # or scoop install pandoc
```

**Calibre** is optional — only needed if you convert MOBI/AZW files:

```bash
# macOS
brew install --cask calibre

# Ubuntu / Debian
sudo apt install calibre

# Windows
choco install calibre
```

### Install TOMD

```bash
# Clone or download this repo, then:
cd TOMD
pip install .

# Or for development (editable install):
pip install -e .
```

## Usage

```bash
# Convert all supported files in the current directory
tomd

# Overwrite existing .md files
tomd --force

# Recurse into subdirectories
tomd -r

# Convert specific files
tomd report.pdf slides.pptx notes.docx

# Output .md files to a specific directory
tomd --output-dir ./markdown

# Combine options
tomd -r -f -o ./converted

# Quiet mode (no banner)
tomd -q
```

### Options

| Flag | Short | Description |
|---|---|---|
| `--force` | `-f` | Overwrite existing `.md` output files |
| `--recursive` | `-r` | Recurse into subdirectories |
| `--output-dir DIR` | `-o DIR` | Write `.md` files to a specific directory |
| `--quiet` | `-q` | Suppress banner, show only results |
| `--version` | `-v` | Show version |
| `--help` | `-h` | Show help |

## How It Works

1. **PDF** files are processed with `pymupdf4llm`, which extracts text while preserving headings, lists, and tables as Markdown.
2. **MOBI/AZW** files are first converted to EPUB via Calibre's `ebook-convert`, then the EPUB is converted to Markdown via Pandoc.
3. **All other formats** are converted directly by Pandoc.

Output files are named `<original_name>.md` and placed alongside the source file (or in `--output-dir` if specified).

## License

MIT
