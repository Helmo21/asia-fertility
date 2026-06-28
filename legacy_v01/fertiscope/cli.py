"""FertiScope CLI: `fertiscope analyze` and `fertiscope demo`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from fertiscope.cost import prices_for_tokenizer
from fertiscope.data import flores_sample
from fertiscope.fertility import FertilityReport, analyze, analyze_all
from fertiscope.tokenizers import TOKENIZERS

console = Console()


def render_report(report: FertilityReport) -> None:
    """Pretty-print one FertilityReport to terminal."""
    title = f"{report.tokenizer_display}"
    table = Table(title=None, show_header=True, header_style="bold cyan", box=None)
    table.add_column("Metric", style="dim")
    table.add_column("English", justify="right")
    table.add_column("Vietnamese", justify="right")
    table.add_column("Ratio (VI/EN)", justify="right", style="bold")

    ratio = report.fertility_ratio

    def fmt_ratio(r: float) -> str:
        color = "green" if r < 1.3 else "yellow" if r < 2.0 else "red"
        return f"[{color}]{r:.2f}x[/{color}]"

    table.add_row("Words", str(report.en.words), str(report.vi.words),
                  f"{report.vi.words / report.en.words:.2f}x" if report.en.words else "n/a")
    table.add_row("Tokens", str(report.en.tokens), str(report.vi.tokens),
                  f"{report.vi.tokens / report.en.tokens:.2f}x" if report.en.tokens else "n/a")
    table.add_row("Fertility (tok/word)",
                  f"{report.en.fertility:.2f}",
                  f"{report.vi.fertility:.2f}",
                  fmt_ratio(ratio))

    cost_panel_lines = []
    for price in prices_for_tokenizer(report.tokenizer_id):
        if price.input_per_1m_usd == 0:
            continue
        en_cost = price.input_per_1m_usd * report.en.tokens / 1_000_000
        vi_cost = price.input_per_1m_usd * report.vi.tokens / 1_000_000
        cost_panel_lines.append(
            f"{price.provider} {price.model}: EN ${en_cost:.6f} | VI ${vi_cost:.6f} "
            f"| VI/EN = {ratio:.2f}x"
        )

    ctx_lines = []
    for cw, ctx in [(4096, report.context_4096), (8192, report.context_8192)]:
        ctx_lines.append(
            f"  ctx={cw}: VI avg example ~{ctx.avg_tokens_per_example:.0f} tok -> "
            f"{ctx.max_examples} examples fit; turn 5 consumes "
            f"{ctx.utilization_curve[4][1]:.1f}% of context, turn 10 consumes "
            f"{ctx.utilization_curve[9][1]:.1f}%."
        )

    console.print(Panel(table, title=title, border_style="cyan"))
    if cost_panel_lines:
        console.print(Panel("\n".join(cost_panel_lines), title="Cost (input only, USD per corpus)",
                            border_style="green"))
    console.print(Panel("\n".join(ctx_lines), title="Context budget",
                        border_style="magenta"))
    if report.notes:
        console.print(Panel("\n".join(f"- {n}" for n in report.notes),
                            title="Notes", border_style="yellow"))


def cmd_demo(args) -> int:
    """Run the EN <-> VI FLORES sample through all 4 launch tokenizers."""
    en = flores_sample.en_text()
    vi = flores_sample.vi_text()
    console.print(Panel(
        f"FLORES-200 EN<->VI sample, {flores_sample.sentence_count()} sentence pairs.\n"
        f"  EN: {len(en)} chars | VI: {len(vi)} chars",
        title="Corpus", border_style="blue"))

    tokenizer_ids = args.tokenizers if args.tokenizers else list(TOKENIZERS.keys())
    for tid in tokenizer_ids:
        try:
            report = analyze(en, vi, tid)
            render_report(report)
        except Exception as exc:
            console.print(Panel(
                f"[red]Failed to analyze with {tid}:[/red]\n{exc}",
                title=f"{tid} [ERROR]", border_style="red"))
    return 0


def cmd_analyze(args) -> int:
    """Analyze a (en, vi) corpus pair through one tokenizer."""
    en_path = Path(args.en)
    vi_path = Path(args.vi)
    if not en_path.is_file() or not vi_path.is_file():
        console.print(f"[red]Both --en and --vi must be readable files.[/red]")
        return 2
    en = en_path.read_text(encoding="utf-8")
    vi = vi_path.read_text(encoding="utf-8")
    report = analyze(en, vi, args.tokenizer)
    render_report(report)
    return 0


def cmd_list_tokenizers(args) -> int:
    table = Table(title="FertiScope v0.1 tokenizers", show_header=True, header_style="bold cyan")
    table.add_column("id")
    table.add_column("family")
    table.add_column("display name")
    table.add_column("notes")
    for spec in TOKENIZERS.values():
        table.add_row(spec.id, spec.family, spec.display_name, spec.notes)
    console.print(table)
    return 0


def cmd_serve(args) -> int:
    """Start the local FastAPI web UI on http://localhost:<port>."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn not installed. Run:[/red] pip install 'fertiscope[web]' "
                      "or: pip install fastapi 'uvicorn[standard]' jinja2")
        return 2
    console.print(Panel(
        f"FertiScope web UI → http://{args.host}:{args.port}\n"
        f"Press Ctrl+C to stop.",
        title="Serving", border_style="cyan"))
    uvicorn.run("fertiscope.web.app:app", host=args.host, port=args.port,
                reload=args.reload, log_level="info")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fertiscope",
                                     description="Tokenizer fertility analysis for EN <-> VI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Run the bundled FLORES-200 EN<->VI sample through all tokenizers.")
    p_demo.add_argument("--tokenizers", nargs="+", choices=list(TOKENIZERS.keys()),
                        help="Subset of tokenizers to run (default: all).")
    p_demo.set_defaults(func=cmd_demo)

    p_an = sub.add_parser("analyze", help="Analyze a (en, vi) corpus pair through one tokenizer.")
    p_an.add_argument("--en", required=True, help="Path to English corpus file (UTF-8 text).")
    p_an.add_argument("--vi", required=True, help="Path to Vietnamese parallel corpus file (UTF-8 text).")
    p_an.add_argument("--tokenizer", required=True, choices=list(TOKENIZERS.keys()))
    p_an.set_defaults(func=cmd_analyze)

    p_ls = sub.add_parser("list-tokenizers", help="List available tokenizers.")
    p_ls.set_defaults(func=cmd_list_tokenizers)

    p_serve = sub.add_parser("serve", help="Start the local web UI on http://localhost:<port>.")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true", help="Auto-reload on file changes (dev).")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
