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

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tomd import __version__
from tomd.converter import (
    ALL_SUPPORTED,
    PDF_EXTENSIONS,
    ConversionResult,
    check_pandoc,
    convert_file,
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


def _convert_with_progress(
    targets: list[Path],
    out_path: Path | None,
    force: bool,
    cwd: Path,
) -> list[ConversionResult]:
    """Convert files with scrolling line-by-line output and per-file PDF progress."""
    results: list[ConversionResult] = []
    total = len(targets)
    converted = skipped = failed = 0

    for i, target in enumerate(targets, 1):
        try:
            display_name = str(target.relative_to(cwd))
        except ValueError:
            display_name = target.name
        short_name = _truncate(display_name, 50)

        ext = target.suffix.lower()
        is_pdf = ext in PDF_EXTENSIONS
        prefix = f"  [dim][{i}/{total}][/dim]"

        if is_pdf:
            # ── Per-file live progress for PDFs ──────────────────────
            page_ref: list[tuple[int, int]] = [(0, 0)]
            live_ref: list = [None]

            def _on_page(cur: int, tot: int) -> None:
                page_ref[0] = (cur, tot)
                if live_ref[0] is None:
                    return
                filled = int(cur / tot * 20) if tot else 0
                bar = "█" * filled + "░" * (20 - filled)
                live_ref[0].update(
                    Text.from_markup(
                        f"{prefix} [cyan]{short_name}[/cyan]  "
                        f"[dim]page {cur}/{tot}[/dim]  {bar}"
                    )
                )

            with Live(
                Text.from_markup(f"{prefix} [cyan]{short_name}[/cyan]  [dim]starting…[/dim]"),
                console=console,
                refresh_per_second=12,
                transient=True,
            ) as live:
                live_ref[0] = live
                result = convert_file(target, output_dir=out_path, force=force, on_page=_on_page)
        else:
            result = convert_file(target, output_dir=out_path, force=force, on_page=None)

        results.append(result)

        # ── Print permanent result line ───────────────────────────────
        if result.success:
            out_name = result.output.name if result.output else ""
            console.print(f"{prefix} [green]✓[/green]  {short_name}  [dim]→ {out_name}[/dim]")
            converted += 1
        elif result.skipped:
            console.print(f"{prefix} [yellow]⊘[/yellow]  {short_name}  [dim](exists — use --force)[/dim]")
            skipped += 1
        else:
            err = (result.error or "Unknown error")[:80]
            console.print(f"{prefix} [red]✗[/red]  {short_name}  [dim]{err}[/dim]")
            failed += 1

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
