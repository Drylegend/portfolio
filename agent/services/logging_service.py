"""
logging_service.py — Structured terminal output and file logging.

Uses Rich for all terminal output. Writes JSON-Lines to daily log files.
No agent or service calls print() directly.
"""

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme
from rich.rule import Rule


_THEME = Theme({
    "info":    "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error":   "bold red",
    "step":    "bold blue",
    "dim":     "dim white",
    "agent":   "bold magenta",
    "header":  "bold white on blue",
})


class LoggingService:
    """
    Rich-powered logger with dual output:
    - Terminal: coloured, formatted output via Rich
    - File: one JSON-Lines file per day in agent/memory/logs/
    """

    def __init__(self, config, time_service):
        self._config = config
        self._time = time_service
        self._console = Console(theme=_THEME)
        self._level = config.log_level  # DEBUG | INFO | WARNING | ERROR

        log_dir = Path(__file__).parent.parent / "memory" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = log_dir / f"{time_service.date_str()}.jsonl"

    # ── Public API ────────────────────────────────────────────────────────────

    def header(self, title: str, subtitle: str = "") -> None:
        """Print the agent launch banner."""
        self._console.print()
        self._console.print(Panel(
            f"[bold white]{title}[/]\n[dim]{subtitle}[/]" if subtitle else f"[bold white]{title}[/]",
            style="header",
            expand=False,
        ))
        self._console.print()

    def step(self, step_num: int, total: int, message: str) -> None:
        """Print a pipeline step header."""
        self._console.print(Rule(f"[step]Step {step_num}/{total} · {message}[/]"))
        self._write("STEP", message, {"step": step_num, "total": total})

    def info(self, message: str, **ctx) -> None:
        self._console.print(f"  [info]ℹ[/]  {message}")
        self._write("INFO", message, ctx)

    def success(self, message: str, **ctx) -> None:
        self._console.print(f"  [success]✔[/]  {message}")
        self._write("SUCCESS", message, ctx)

    def warning(self, message: str, **ctx) -> None:
        self._console.print(f"  [warning]⚠[/]  {message}")
        self._write("WARNING", message, ctx)

    def error(self, message: str, **ctx) -> None:
        self._console.print(f"  [error]✖[/]  {message}")
        self._write("ERROR", message, ctx)

    def agent(self, agent_name: str, message: str, **ctx) -> None:
        """Log a message attributed to a specific agent."""
        self._console.print(f"  [agent][{agent_name}][/]  {message}")
        self._write("AGENT", message, {"agent": agent_name, **ctx})

    def print(self, message: str) -> None:
        """Raw Rich-formatted print (use sparingly)."""
        self._console.print(message)

    def blank(self) -> None:
        self._console.print()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _write(self, level: str, message: str, ctx: dict) -> None:
        """Append a structured log entry to today's JSONL file."""
        entry = {
            "ts":      self._time.now_iso(),
            "level":   level,
            "message": message,
            **{k: v for k, v in ctx.items() if v is not None},
        }
        try:
            with open(self._log_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass  # never crash the pipeline because of a log write
