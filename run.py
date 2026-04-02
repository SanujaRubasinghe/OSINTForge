#!/usr/bin/env python3
"""
OSINTForge CLI runner.

Usage:
    python run.py --query "Acme Corp" --type org
    python run.py --query "john.doe@example.com" --type person
    python run.py --query "acme.com" --type domain --image ./photo.jpg
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from orchestrator.graph import build_graph_in_memory
from orchestrator.state import OSINTState
from orchestrator.checkpointer import CheckpointConfig
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import uuid

console = Console()


def _build_initial_state(query: str, target_type: str,
                          image_path: str | None) -> OSINTState:
    return {
        "query":               query,
        "target_type":         target_type,
        "input_image_path":    image_path,
        "collection_tasks":    [],
        "planner_notes":       "",
        "findings":            [],
        "entities":            [],
        "relationships":       [],
        "exif_data":           None,
        "reverse_search_urls": None,
        "visual_analysis":     None,
        "ocr_text":            None,
        "detected_logos":      None,
        "draft_report":        None,
        "critic_feedback":     None,
        "refinement_count":    0,
        "final_report":        None,
        "errors":              [],
        "agent_trace":         [],
        "status":              "planning",
    }


async def _run(query: str, target_type: str, image_path: str | None,
               output_json: bool, output_file: str | None):
    console.print(Panel(
        f"[bold]OSINTForge[/bold]\n"
        f"Target: [cyan]{query}[/cyan]  Type: [green]{target_type}[/green]",
        expand=False,
    ))

    graph      = build_graph_in_memory()
    task_id    = str(uuid.uuid4())
    config     = CheckpointConfig.for_stream(task_id)
    state      = _build_initial_state(query, target_type, image_path)
    final      = None
    step_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Initialising agents...", total=None)

        async for current_state in graph.astream(
            state, config=config, stream_mode="values"
        ):
            trace = current_state.get("agent_trace", [])
            if len(trace) > step_count:
                for step in trace[step_count:]:
                    agent  = step.get("agent", "?")
                    action = step.get("action", "")
                    progress.update(task, description=f"[cyan]{agent}[/cyan] → {action}")
                step_count = len(trace)
            final = current_state

    if not final:
        console.print("[red]Run failed — no state returned.[/red]")
        sys.exit(1)

    errors = final.get("errors", [])
    if errors:
        for e in errors:
            console.print(f"[red]Error:[/red] {e}")

    report = final.get("final_report")
    if not report:
        console.print("[yellow]No report generated.[/yellow]")
        _print_trace(final.get("agent_trace", []))
        sys.exit(1)

    if output_json:
        out = json.dumps(report, indent=2, default=str)
        if output_file:
            with open(output_file, "w") as f:
                f.write(out)
            console.print(f"[green]Report saved to {output_file}[/green]")
        else:
            print(out)
        return

    _print_report(report)
    _print_trace(final.get("agent_trace", []))


def _print_report(report: dict):
    console.print("\n[bold underline]Intelligence Report[/bold underline]")
    console.print(f"[bold]Target:[/bold] {report['target']}")
    console.print(f"[bold]Confidence:[/bold] {report.get('confidence_overall', 0):.0%}")
    console.print(f"[bold]Generated:[/bold] {report.get('generated_at', '')}\n")

    console.print(Panel(report.get("summary", "No summary."), title="Summary"))

    # Entities table
    entities = report.get("entities", [])
    if entities:
        tbl = Table(title=f"Entities ({len(entities)})", show_lines=False)
        tbl.add_column("Type",       style="cyan",  width=12)
        tbl.add_column("Name",       style="white", width=30)
        tbl.add_column("Confidence", style="green", width=12)
        tbl.add_column("Sources",    style="dim",   width=8)
        for e in sorted(entities, key=lambda x: x["confidence"], reverse=True)[:20]:
            tbl.add_row(
                e["type"], e["name"],
                f"{e['confidence']:.0%}",
                str(len(e.get("sources", []))),
            )
        console.print(tbl)

    # Claims
    claims = report.get("claims", [])
    if claims:
        console.print(f"\n[bold]Claims ({len(claims)}):[/bold]")
        for c in sorted(claims, key=lambda x: x["confidence"], reverse=True)[:15]:
            flag = " [red][FLAGGED][/red]" if c.get("flagged") else ""
            console.print(
                f"  [dim]{c['confidence']:.0%}[/dim] {c['text'][:120]}{flag}"
            )

    # Gaps
    gaps = report.get("gaps", [])
    if gaps:
        console.print("\n[bold yellow]Intelligence gaps:[/bold yellow]")
        for g in gaps:
            console.print(f"  • {g}")


def _print_trace(trace: list[dict]):
    if not trace:
        return
    tbl = Table(title="Agent trace", show_lines=False)
    tbl.add_column("#",         style="dim",   width=4)
    tbl.add_column("Agent",     style="cyan",  width=18)
    tbl.add_column("Action",    style="white", width=22)
    tbl.add_column("Details",   style="dim",   width=40)
    for i, step in enumerate(trace, 1):
        details = ", ".join(
            f"{k}={v}" for k, v in step.items()
            if k not in ("agent", "action", "timestamp", "tasks", "error")
            and v not in (None, [], {}, "")
        )[:50]
        tbl.add_row(str(i), step.get("agent", ""), step.get("action", ""), details)
    console.print(tbl)


def main():
    parser = argparse.ArgumentParser(
        description="OSINTForge CLI — multi-agent OSINT synthesis"
    )
    parser.add_argument("--query",  "-q", required=True, help="Target entity")
    parser.add_argument("--type",   "-t", default="org",
                        choices=["org", "person", "domain", "topic"])
    parser.add_argument("--image",  "-i", default=None,
                        help="Path to image file for image intelligence")
    parser.add_argument("--json",   "-j", action="store_true",
                        help="Output report as JSON")
    parser.add_argument("--output", "-o", default=None,
                        help="Save report JSON to file")
    args = parser.parse_args()

    asyncio.run(_run(args.query, args.type, args.image, args.json, args.output))


if __name__ == "__main__":
    main()
