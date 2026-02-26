"""
CLI entry point for TOMD.

Usage:
    tomd                        # convert all supported files in current dir
    tomd --force                # overwrite existing .md files
    tomd -r                     # recurse into subdirectories
    tomd file1.pdf file2.docx   # convert specific files
    tomd --output-dir ./md      # write output to a specific directory
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import click
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from tomd import __version__
from tomd.converter import (
    ALL_SUPPORTED,
    PDF_EXTENSIONS,
    ConversionResult,
    check_pandoc,
    convert_file,
    get_pdf_page_count,
    is_supported,
    pandoc_install_hint,
)

console = Console()


def _collect_files(
    directory: Path,
    recursive: bool = False,
) -> list[Path]:
    """Collect all supported files in a directory."""
    if recursive:
        files = sorted(
            f
            for f in directory.rglob("*")
            if f.is_file() and is_supported(f)
        )
    else:
        files = sorted(
            f
            for f in directory.iterdir()
            if f.is_file() and is_supported(f)
        )
    return files


def _truncate(name: str, max_len: int = 50) -> str:
    """Truncate a filename for display, keeping extension visible."""
    if len(name) <= max_len:
        return name
    stem, dot, ext = name.rpartition(".")
    if dot:
        keep = max_len - len(ext) - 4  # room for "…" + "." + ext
        return f"{stem[:keep]}….{ext}"
    return name[: max_len - 1] + "…"


def _build_live_table(
    results: list[ConversionResult], cwd: Path
) -> Table:
    """Build a Rich table from completed results so far."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        title_style="bold white",
        expand=False,
        padding=(0, 1),
    )
    table.add_column("File", style="white", no_wrap=False, max_width=40)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Details", style="dim", no_wrap=False, max_width=40)

    for r in results:
        try:
            name = str(r.source.relative_to(cwd))
        except ValueError:
            name = r.source.name
        name = _truncate(name, 38)

        if r.success:
            status = "[bold green]✓ Done[/bold green]"
            detail = f"→ {r.output.name}" if r.output else ""
        elif r.skipped:
            status = "[yellow]⊘ Skip[/yellow]"
            detail = "exists (--force)"
        else:
            status = "[bold red]✗ Fail[/bold red]"
            # Truncate long error messages for the live view
            err = r.error or "Unknown error"
            detail = err[:60] + "…" if len(err) > 60 else err

        table.add_row(name, status, detail)

    return table


def _print_banner() -> None:
    """Print the app banner."""
    console.print(
        Panel(
            f"[bold cyan]TOMD[/bold cyan]  [dim]v{__version__}[/dim]\n"
            "[white]Universal Document → Markdown Converter[/white]",
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _build_layout(
    results_table: Table | None,
    file_text: Text,
    file_progress: Progress,
    page_text: Text,
    status_text: Text,
) -> Group:
    """Assemble the live display layout."""
    parts: list = []
    if results_table is not None and results_table.row_count > 0:
        parts.append(results_table)
        parts.append(Text(""))  # spacer
    parts.append(file_text)
    parts.append(file_progress)
    if page_text.plain:  # only show page line if it has content
        parts.append(page_text)
    parts.append(status_text)
    return Group(*parts)


def _convert_with_progress(
    targets: list[Path],
    out_path: Path | None,
    force: bool,
    cwd: Path,
) -> list[ConversionResult]:
    """Convert files with a live progress display and results table."""
    results: list[ConversionResult] = []
    total = len(targets)

    # ── File-level progress bar ──
    file_progress = Progress(
        SpinnerColumn("dots", style="cyan"),
        BarColumn(bar_width=40, style="dim", complete_style="cyan", finished_style="green"),
        MofNCompleteColumn(),
        TextColumn("│"),
        TimeElapsedColumn(),
        console=console,
    )
    file_task = file_progress.add_task("Files", total=total)

    # ── Mutable display elements ──
    file_text = Text()
    page_text = Text()
    status_text = Text()
    results_table: Table | None = None

    live_ref: Live | None = None  # capture for the page callback

    def _on_page(current: int, total_pages: int) -> None:
        """Callback invoked per PDF page — updates page_text in place."""
        nonlocal page_text
        pct = int(current / total_pages * 100) if total_pages else 0
        filled = int(current / total_pages * 20) if total_pages else 0
        bar = "█" * filled + "░" * (20 - filled)
        page_text = Text.from_markup(
            f"  [dim]Pages:[/dim]  {bar}  [bold]{current}[/bold][dim]/{total_pages}[/dim]  [dim]({pct}%)[/dim]"
        )
        if live_ref:
            live_ref.update(
                _build_layout(results_table, file_text, file_progress, page_text, status_text)
            )

    with Live(
        _build_layout(results_table, file_text, file_progress, page_text, status_text),
        console=console,
        refresh_per_second=12,
        transient=True,
    ) as live:
        live_ref = live
        converted = skipped = failed = 0

        for target in targets:
            # ── Current file label ──
            try:
                display_name = str(target.relative_to(cwd))
            except ValueError:
                display_name = target.name
            short_name = _truncate(display_name)

            ext = target.suffix.lower()
            is_pdf = ext in PDF_EXTENSIONS

            file_text = Text.from_markup(
                f"  [dim]File:[/dim] [cyan]{short_name}[/cyan]"
                + ("  [dim](PDF — page-by-page)[/dim]" if is_pdf else "")
            )

            # Reset page progress for this file
            page_text = Text()

            live.update(
                _build_layout(results_table, file_text, file_progress, page_text, status_text)
            )

            # ── Convert ──
            result = convert_file(
                target,
                output_dir=out_path,
                force=force,
                on_page=_on_page if is_pdf else None,
            )
            results.append(result)

            # ── Update counters ──
            if result.success:
                converted += 1
            elif result.skipped:
                skipped += 1
            else:
                failed += 1

            # ── Rebuild live results table ──
            results_table = _build_live_table(results, cwd)

            # ── Tally line ──
            parts = []
            if converted:
                parts.append(f"[green]✓ {converted} converted[/green]")
            if skipped:
                parts.append(f"[yellow]⊘ {skipped} skipped[/yellow]")
            if failed:
                parts.append(f"[red]✗ {failed} failed[/red]")
            status_text = Text.from_markup(f"  {'  │  '.join(parts)}")

            # Clear page text now that this file is done
            page_text = Text()

            file_progress.advance(file_task)
            live.update(
                _build_layout(results_table, file_text, file_progress, page_text, status_text)
            )

    return results


def _print_final_summary(results: list[ConversionResult], cwd: Path) -> None:
    """Print the final summary after the live display is cleared."""
    if not results:
        console.print("[dim]No supported files found.[/dim]")
        return

    table = _build_live_table(results, cwd)
    console.print()
    console.print(table)

    converted = sum(1 for r in results if r.success)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.success and not r.skipped)

    parts = []
    if converted:
        parts.append(f"[green]{converted} converted[/green]")
    if skipped:
        parts.append(f"[yellow]{skipped} skipped[/yellow]")
    if failed:
        parts.append(f"[red]{failed} failed[/red]")
    console.print(f"\n  {'  •  '.join(parts)}\n")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-v", "--version", prog_name="tomd")
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Overwrite existing .md output files.",
)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    default=False,
    help="Recurse into subdirectories.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=None,
    help="Write .md files to this directory (default: ./md-done).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress banner and show only results.",
)
def main(
    files: tuple[str, ...],
    force: bool,
    recursive: bool,
    output_dir: str | None,
    quiet: bool,
) -> None:
    """Convert document files to Markdown.

    If no FILES are given, converts all supported files in the current
    directory. Supported formats include: PDF, DOCX, EPUB, MOBI, ODT,
    RTF, HTML, LaTeX, RST, and many more.
    """
    if not quiet:
        _print_banner()

    cwd = Path.cwd()
    out_path = Path(output_dir) if output_dir else cwd / "md-done"

    # Check for Pandoc early
    if not check_pandoc():
        console.print(
            f"[bold yellow]⚠  Pandoc not found.[/bold yellow]\n"
            f"   Most formats require Pandoc. Install it:\n"
            f"   [cyan]{pandoc_install_hint()}[/cyan]\n"
        )

    # Collect files
    if files:
        targets = [Path(f) for f in files]
        # Validate they are supported
        unsupported = [t for t in targets if not is_supported(t)]
        if unsupported:
            console.print("[bold yellow]⚠  Unsupported files:[/bold yellow]")
            for u in unsupported:
                console.print(f"   • {u.name}")
            console.print(
                f"   Supported extensions: {', '.join(sorted(ALL_SUPPORTED))}\n"
            )
            targets = [t for t in targets if is_supported(t)]
    else:
        targets = _collect_files(cwd, recursive=recursive)

    if not targets:
        console.print("[dim]No supported files found in this directory.[/dim]")
        exts = ", ".join(sorted(ALL_SUPPORTED))
        console.print(f"[dim]Supported: {exts}[/dim]")
        sys.exit(0)

    console.print(
        f"  [dim]Found[/dim] [bold]{len(targets)}[/bold] [dim]file(s) to convert…[/dim]\n"
    )

    # Convert with live progress
    results = _convert_with_progress(targets, out_path, force, cwd)

    _print_final_summary(results, cwd)

    # Exit code: 1 if any failures
    if any(not r.success and not r.skipped for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
