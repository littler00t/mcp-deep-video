from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent

from .agent import create_agent
from .models import Severity, WorkoutAnalysis

load_dotenv()

console = Console()


def _format_tool_args(args: str | dict | None) -> str:
    if args is None:
        return ""
    if isinstance(args, dict):
        parts = [f"{k}={v!r}" for k, v in args.items()]
        return "(" + ", ".join(parts) + ")"
    try:
        d = json.loads(args)
        parts = [f"{k}={v!r}" for k, v in d.items()]
        return "(" + ", ".join(parts) + ")"
    except Exception:
        return f"({args})"


async def _run_analysis(video_path: Path) -> None:
    console.print(f"\n[bold cyan]Workout Judge (MCP)[/bold cyan] \u2014 analyzing [yellow]{video_path.name}[/yellow]\n")

    video_path = video_path.resolve()
    if not video_path.is_file():
        console.print(f"[bold red]Error:[/bold red] File not found: {video_path}")
        raise SystemExit(1)

    video_root = str(video_path.parent)
    filename = video_path.name

    agent, mcp_server = create_agent(video_root)

    prompt = (
        f"Please analyze the workout technique in the video file '{filename}'. "
        f"Use '{filename}' as the filename argument for all tool calls. "
        f"Follow the required analysis sequence: overview first, then sections, then precise frames."
    )

    tool_history: list[str] = []
    current_spinner_text: list[str] = ["Starting MCP server..."]
    result: WorkoutAnalysis | None = None

    with Live(console=console, refresh_per_second=8) as live:

        def _render() -> Text:
            lines = Text()
            for line in tool_history:
                lines.append(line + "\n")
            if current_spinner_text[0]:
                lines.append(f"  {current_spinner_text[0]}", style="dim cyan")
            return lines

        live.update(_render())

        current_spinner_text[0] = "Initializing..."
        live.update(_render())

        async with agent.iter(prompt) as agent_run:
            async for node in agent_run:
                if agent.is_call_tools_node(node):
                    async with node.stream(agent_run.ctx) as stream:
                        async for event in stream:
                            if isinstance(event, FunctionToolCallEvent):
                                tool_name = event.part.tool_name
                                args_str = _format_tool_args(event.part.args)
                                current_spinner_text[0] = f"[bold]{tool_name}[/bold]{args_str} ..."
                                live.update(_render())

                            elif isinstance(event, FunctionToolResultEvent):
                                tool_name = event.result.tool_name
                                return_str = event.result.model_response_str()
                                if len(return_str) > 80:
                                    return_str = return_str[:77] + "..."
                                tool_history.append(
                                    f"  [green]\u2713[/green] [bold]{tool_name}[/bold] \u2014 {return_str}"
                                )
                                current_spinner_text[0] = "Thinking..."
                                live.update(_render())

        current_spinner_text[0] = ""
        live.update(_render())

        if agent_run.result and agent_run.result.output:
            result = agent_run.result.output

    if result is None:
        console.print("[bold red]Analysis failed \u2014 no result returned.[/bold red]")
        raise SystemExit(1)

    _render_results(result)


def _render_results(analysis: WorkoutAnalysis) -> None:
    console.print()

    score = analysis.technique_score
    if score >= 7:
        score_color = "green"
    elif score >= 4:
        score_color = "yellow"
    else:
        score_color = "red"

    level_color = {"beginner": "cyan", "intermediate": "yellow", "advanced": "green"}.get(
        analysis.athlete_level, "white"
    )

    header_text = Text()
    header_text.append(f" {analysis.exercise_name} ", style="bold white")
    header_text.append(" \u2502 ", style="dim")
    header_text.append(f"{analysis.duration_analyzed}", style="dim")
    header_text.append(" \u2502 ", style="dim")
    header_text.append(f"{analysis.athlete_level.upper()}", style=f"bold {level_color}")
    header_text.append(" \u2502 ", style="dim")
    header_text.append("SCORE: ", style="bold")
    header_text.append(f"{score}/10", style=f"bold {score_color}")

    console.print(Panel(header_text, title="[bold]Workout Analysis[/bold]", border_style="cyan"))
    console.print()

    console.print(Panel(analysis.overall_assessment, title="Overall Assessment", border_style="blue"))
    console.print()

    if analysis.observations:
        obs_table = Table(
            show_header=True,
            header_style="bold",
            border_style="dim",
            expand=True,
        )
        obs_table.add_column("Time", style="dim", width=12)
        obs_table.add_column("Body Part", width=14)
        obs_table.add_column("Observation", ratio=1)
        obs_table.add_column("Severity", width=14)

        severity_styles = {
            Severity.positive: ("green", "\u2713 POSITIVE"),
            Severity.minor_issue: ("yellow", "\u26a0 MINOR"),
            Severity.major_issue: ("red", "\u2717 MAJOR"),
        }

        for obs in analysis.observations:
            sev_color, sev_label = severity_styles.get(obs.severity, ("white", obs.severity.value))
            obs_table.add_row(
                obs.timestamp_range,
                obs.body_part,
                obs.observation,
                Text(sev_label, style=f"bold {sev_color}"),
            )

        console.print(Panel(obs_table, title="Observations", border_style="yellow"))
        console.print()

    strengths_text = "\n".join(f"[green]\u2022[/green] {s}" for s in analysis.strengths) or "[dim]None noted[/dim]"
    improvements_text = "\n".join(f"[yellow]\u2022[/yellow] {a}" for a in analysis.areas_for_improvement) or "[dim]None noted[/dim]"

    strengths_panel = Panel(
        strengths_text,
        title="[bold green]Strengths[/bold green]",
        border_style="green",
        expand=True,
    )
    improvements_panel = Panel(
        improvements_text,
        title="[bold yellow]Areas for Improvement[/bold yellow]",
        border_style="yellow",
        expand=True,
    )
    console.print(Columns([strengths_panel, improvements_panel]))
    console.print()

    if analysis.key_recommendations:
        recs_text = "\n".join(
            f"[bold cyan]{i}.[/bold cyan] {r}"
            for i, r in enumerate(analysis.key_recommendations, 1)
        )
        console.print(Panel(recs_text, title="[bold]Key Recommendations[/bold]", border_style="cyan"))
        console.print()


@click.group()
def cli() -> None:
    """Workout Judge (MCP) \u2014 AI-powered exercise form analysis via MCP server."""


@cli.command()
@click.argument("video_path", type=click.Path(exists=True, readable=True, path_type=Path))
def analyze(video_path: Path) -> None:
    """Analyze exercise form in a workout video."""
    asyncio.run(_run_analysis(video_path))
