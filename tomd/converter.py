"""
Conversion engine for TOMD.

Routes each file to the appropriate converter based on extension:
- PDF  → pymupdf4llm (high-quality markdown extraction)
- MOBI → Calibre ebook-convert → temp EPUB → Pandoc
- Everything else (docx, epub, odt, rtf, html, etc.) → Pandoc
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

console = Console()

# ── Format registries ────────────────────────────────────────────────────────

# Formats handled by Pandoc (extension → pandoc input format name)
PANDOC_FORMATS: dict[str, str] = {
    ".docx": "docx",
    ".epub": "epub",
    ".odt": "odt",
    ".rtf": "rtf",
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".tex": "latex",
    ".latex": "latex",
    ".rst": "rst",
    ".textile": "textile",
    ".mediawiki": "mediawiki",
    ".wiki": "mediawiki",
    ".docbook": "docbook",
    ".dbk": "docbook",
    ".xml": "docbook",
    ".fb2": "fb2",
    ".opml": "opml",
    ".org": "org",
    ".txt": "markdown",
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".ipynb": "ipynb",
    ".pptx": "pptx",
}

PDF_EXTENSIONS = {".pdf"}

MOBI_EXTENSIONS = {".mobi", ".azw", ".azw3"}

ALL_SUPPORTED = set(PANDOC_FORMATS.keys()) | PDF_EXTENSIONS | MOBI_EXTENSIONS


def is_supported(path: Path) -> bool:
    """Check whether a file has a supported extension."""
    return path.suffix.lower() in ALL_SUPPORTED


# ── Dependency checks ────────────────────────────────────────────────────────

def check_pandoc() -> bool:
    """Return True if pandoc is available on PATH."""
    return shutil.which("pandoc") is not None


def check_calibre() -> bool:
    """Return True if Calibre's ebook-convert is available on PATH."""
    return shutil.which("ebook-convert") is not None


def pandoc_install_hint() -> str:
    """Return platform-specific install instructions for Pandoc."""
    import platform

    system = platform.system()
    if system == "Darwin":
        return "brew install pandoc"
    elif system == "Linux":
        return "sudo apt install pandoc   # or your distro's package manager"
    elif system == "Windows":
        return "choco install pandoc   # or scoop install pandoc, or download from https://pandoc.org"
    return "Visit https://pandoc.org/installing.html"


def calibre_install_hint() -> str:
    """Return platform-specific install instructions for Calibre."""
    import platform

    system = platform.system()
    if system == "Darwin":
        return "brew install --cask calibre"
    elif system == "Linux":
        return "sudo apt install calibre"
    elif system == "Windows":
        return "choco install calibre   # or download from https://calibre-ebook.com"
    return "Visit https://calibre-ebook.com/download"


# ── Converters ───────────────────────────────────────────────────────────────

def get_pdf_page_count(source: Path) -> int:
    """Return the number of pages in a PDF without converting it."""
    import pymupdf  # type: ignore

    doc = pymupdf.open(str(source))
    count = len(doc)
    doc.close()
    return count


def convert_pdf(
    source: Path,
    on_page: callable | None = None,
) -> str:
    """Convert a PDF file to Markdown via pymupdf4llm, page by page.

    Parameters
    ----------
    on_page : callable | None
        Optional callback ``(current_page, total_pages) -> None``
        called after each page is processed.
    """
    import pymupdf  # type: ignore
    import pymupdf4llm  # type: ignore

    doc = pymupdf.open(str(source))
    total_pages = len(doc)
    doc.close()

    if on_page is None:
        # Fast path — convert everything at once
        return pymupdf4llm.to_markdown(str(source))

    # Page-by-page for progress reporting
    chunks: list[str] = []
    for page_num in range(total_pages):
        chunk: str = pymupdf4llm.to_markdown(str(source), pages=[page_num])
        chunks.append(chunk)
        on_page(page_num + 1, total_pages)

    return "\n".join(chunks)


def convert_with_pandoc(source: Path) -> str:
    """Convert a file to Markdown via pypandoc / Pandoc."""
    import pypandoc  # type: ignore

    ext = source.suffix.lower()
    input_format = PANDOC_FORMATS.get(ext)

    extra_args = ["--wrap=none", "--standalone"]

    output: str = pypandoc.convert_file(
        str(source),
        to="markdown",
        format=input_format,
        extra_args=extra_args,
    )
    return output


def convert_mobi(source: Path) -> str:
    """Convert a MOBI/AZW file to Markdown via Calibre → EPUB → Pandoc."""
    with tempfile.TemporaryDirectory() as tmpdir:
        epub_path = os.path.join(tmpdir, "converted.epub")

        # Step 1: MOBI → EPUB via Calibre
        result = subprocess.run(
            ["ebook-convert", str(source), epub_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ebook-convert failed for {source.name}:\n{result.stderr}"
            )

        # Step 2: EPUB → Markdown via Pandoc
        import pypandoc  # type: ignore

        output: str = pypandoc.convert_file(
            epub_path,
            to="markdown",
            format="epub",
            extra_args=["--wrap=none", "--standalone"],
        )
        return output


# ── Main dispatch ────────────────────────────────────────────────────────────

class ConversionResult:
    """Result of a single file conversion."""

    __slots__ = ("source", "output", "success", "error", "skipped")

    def __init__(
        self,
        source: Path,
        output: Path | None = None,
        success: bool = False,
        error: str | None = None,
        skipped: bool = False,
    ):
        self.source = source
        self.output = output
        self.success = success
        self.error = error
        self.skipped = skipped


def convert_file(
    source: Path,
    output_dir: Path | None = None,
    force: bool = False,
    on_page: callable | None = None,
) -> ConversionResult:
    """
    Convert a single file to Markdown.

    Parameters
    ----------
    source : Path
        Path to the input file.
    output_dir : Path | None
        Directory for the output `.md` file (defaults to same dir as source).
    force : bool
        If True, overwrite existing `.md` files.
    on_page : callable | None
        Progress callback ``(current_page, total_pages)`` for PDF files.

    Returns
    -------
    ConversionResult
    """
    ext = source.suffix.lower()

    # Determine output path
    dest_dir = output_dir or source.parent
    dest = dest_dir / (source.stem + ".md")

    # Skip if already converted (unless --force)
    if dest.exists() and not force:
        return ConversionResult(source, dest, skipped=True)

    try:
        if ext in PDF_EXTENSIONS:
            md_text = convert_pdf(source, on_page=on_page)
        elif ext in MOBI_EXTENSIONS:
            if not check_calibre():
                return ConversionResult(
                    source,
                    error=(
                        f"MOBI conversion requires Calibre.\n"
                        f"  Install: {calibre_install_hint()}"
                    ),
                )
            md_text = convert_mobi(source)
        elif ext in PANDOC_FORMATS:
            if not check_pandoc():
                return ConversionResult(
                    source,
                    error=(
                        f"Pandoc is required but not found.\n"
                        f"  Install: {pandoc_install_hint()}"
                    ),
                )
            md_text = convert_with_pandoc(source)
        else:
            return ConversionResult(
                source, error=f"Unsupported format: {ext}"
            )

        # Ensure output directory exists
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest.write_text(md_text, encoding="utf-8")
        return ConversionResult(source, dest, success=True)

    except Exception as exc:
        return ConversionResult(source, error=str(exc))

