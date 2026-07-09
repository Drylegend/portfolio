"""
cli.py — All user interaction lives here.

This is the sole entry point and the only file that reads from or writes to
stdout/stdin. No agent, service, or orchestrator component calls input() or print().

Run with:
    python agent/cli.py
"""

import sys
from pathlib import Path

# Ensure agent/ is on Python path
_AGENT_DIR = Path(__file__).parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from rich.console   import Console
from rich.panel     import Panel
from rich.table     import Table
from rich.prompt    import Prompt, Confirm
from rich.syntax    import Syntax
from rich.rule      import Rule

console = Console()


class CLI:
    """
    All user-facing interaction for the Portfolio Agent.

    Methods are named from the user's perspective.
    They receive data, display it, and return user decisions.
    They never call agents or services.
    """

    def __init__(self, logger):
        self._logger = logger

    # ── Display Methods ───────────────────────────────────────────────────────

    def show_header(self, provider: str, model: str) -> None:
        console.print()
        console.print(Panel(
            f"[bold white]Portfolio Agent[/bold white]\n"
            f"[dim]Provider: {provider.title()}  ·  Model: {model}[/dim]",
            style="bold blue",
            expand=False,
        ))
        console.print()

    def step(self, num: int, total: int, message: str) -> None:
        self._logger.step(num, total, message)

    def show_memory_status(self, state: dict) -> None:
        count = len(state.get("projects", []))
        keys  = ", ".join(state.get("known_keys", []))
        self._logger.success(f"Portfolio loaded: {count} project(s) known.")
        if keys:
            self._logger.info(f"Known keys: {keys}")

    def no_new_images(self, duplicates: list[dict]) -> None:
        console.print()
        console.print("[yellow]No new images found in assets/.[/yellow]")
        if duplicates:
            console.print(f"  {len(duplicates)} duplicate(s) detected and skipped.")
        console.print("\n[dim]Add images to assets/ using the naming format:[/dim]")
        console.print("[dim]  <projectkey>_cover.jpg, <projectkey>_img1.jpg, ...[/dim]")
        console.print()

    # ── Image Confirmation ────────────────────────────────────────────────────

    def confirm_image_group(self, group) -> object | None:
        """
        Show detected image group and ask user to confirm or skip.

        Returns confirmed group (possibly with corrected key), or None to skip.
        """
        console.print()
        console.print(Rule(f"[bold]New images detected: '{group.detected_key}'[/bold]"))

        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column("Label", style="dim")
        t.add_column("Value")
        t.add_row("Detected key:", group.detected_key)
        t.add_row("Status:",       "New project" if group.is_new else "Update to existing")
        t.add_row("Confidence:",   group.confidence)
        t.add_row("Cover:",        group.cover or "(none)")
        t.add_row("Gallery:",      str(len(group.images)) + " image(s)")
        t.add_row("All files:",    ", ".join(group.all_files))
        console.print(t)
        console.print()

        action = Prompt.ask(
            "  Action",
            choices=["y", "n", "rename"],
            default="y",
            show_choices=True,
        )

        if action == "n":
            return None

        if action == "rename":
            new_key = Prompt.ask("  Enter correct project key").strip().lower().replace(" ", "_")
            group.detected_key = new_key

        return group

    def skipped(self, key: str) -> None:
        self._logger.info(f"Skipped project: {key}")

    # ── Project Description ───────────────────────────────────────────────────

    def get_project_description(self, group) -> str | None:
        """Prompt user for a project description. Returns None to cancel."""
        console.print()
        console.print(f"[bold]Describe your project:[/bold] [dim](paste as much as you want)[/dim]")
        console.print("[dim]Include: what it does, tech stack, GitHub link, datasets, algorithms, etc.[/dim]")
        console.print("[dim]Enter an empty line when done, or type 'cancel' to abort.[/dim]")
        console.print()

        lines = []
        while True:
            try:
                line = input("  > ")
                if line.strip().lower() == "cancel":
                    return None
                if not line.strip() and lines:
                    break
                lines.append(line)
            except (EOFError, KeyboardInterrupt):
                return None

        if not lines:
            return ""

        # Check if user entered a file path instead of raw text
        if len(lines) == 1:
            raw_path = lines[0].strip().strip('"').strip("'")
            possible_path = Path(raw_path)
            if possible_path.exists() and possible_path.is_file():
                try:
                    content = possible_path.read_text(encoding="utf-8")
                    self._logger.success(f"Loaded description from file: {possible_path.name}")
                    return content
                except Exception as exc:
                    self._logger.error(f"Failed to read description file: {exc}")

        return "\n".join(lines).strip()

    def get_revision_description(self, issues: list[str], instruction: str) -> str:
        """Ask user to revise description after Reflection rejection."""
        console.print()
        console.print("[yellow]Reflection Agent found issues:[/yellow]")
        for issue in issues:
            console.print(f"  [yellow]•[/yellow] {issue}")
        if instruction:
            console.print(f"\n[dim]Suggested fix: {instruction}[/dim]")
        console.print()
        console.print("[bold]Revise your project description[/bold] [dim](or press Enter to keep original):[/dim]")
        lines = []
        while True:
            try:
                line = input("  > ")
                if not line.strip() and lines:
                    break
                if not line.strip() and not lines:
                    return ""
                lines.append(line)
            except (EOFError, KeyboardInterrupt):
                return ""
        return "\n".join(lines).strip()

    def offer_manual_edit(self, metadata) -> bool:
        """Last resort: offer manual metadata edit after max reflection failures."""
        console.print()
        console.print("[red]Reflection Agent rejected metadata after maximum attempts.[/red]")
        return Confirm.ask("  Continue anyway with current metadata?", default=False)

    # ── Metadata Confirmation ─────────────────────────────────────────────────

    def confirm_metadata(self, metadata) -> object | None:
        """Display extracted metadata and ask user to confirm, edit, or cancel."""
        console.print()
        console.print(Rule("[bold]Extracted Project Details[/bold]"))

        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column("Field", style="dim", min_width=16)
        t.add_column("Value")

        t.add_row("Key:",         metadata.key)
        t.add_row("Title:",       metadata.title)
        t.add_row("Short desc:",  metadata.short_desc)
        t.add_row("Full desc:",   metadata.full_desc[:120] + "…" if len(metadata.full_desc) > 120 else metadata.full_desc)
        t.add_row("GitHub:",      metadata.github_url or "(none)")
        t.add_row("Category:",    metadata.category)
        t.add_row("Difficulty:",  metadata.difficulty)
        t.add_row("Year:",        str(metadata.year))
        t.add_row("Tech tags:",   ", ".join(metadata.tech_tags))
        t.add_row("Keywords:",    ", ".join(metadata.keywords[:6]))
        t.add_row("Cover:",       metadata.cover_image)
        t.add_row("Images:",      f"{len(metadata.images)} total")

        console.print(t)
        console.print()

        action = Prompt.ask(
            "  Proceed?",
            choices=["y", "n"],
            default="y",
        )
        return metadata if action == "y" else None

    # ── Validation Display ────────────────────────────────────────────────────

    def show_validation_errors(self, report) -> None:
        console.print()
        console.print("[red bold]Validation failed:[/red bold]")
        for err in report.errors:
            console.print(f"  [red]✖[/red] {err}")
        for warn in report.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warn}")

    def rollback_notice(self) -> None:
        console.print("[yellow]Files have been restored from backup.[/yellow]")

    # ── Smoke Test ────────────────────────────────────────────────────────────

    def smoke_test_failed(self) -> None:
        console.print()
        console.print("[red bold]Smoke test failed.[/red bold]")
        console.print("[yellow]Files have been restored from backup.[/yellow]")

    # ── Deployment ────────────────────────────────────────────────────────────

    def confirm_deployment(self, diff: str, commit_message: str, url: str) -> bool:
        """Show git diff and ask user to confirm push."""
        console.print()
        console.print(Rule("[bold]Git Diff (staged changes)[/bold]"))
        console.print(Syntax(diff, "diff", theme="monokai", line_numbers=False))
        console.print()
        console.print(f"  [dim]Commit message:[/dim] {commit_message}")
        console.print(f"  [dim]Deploy target: [/dim] {url}")
        console.print()
        return Confirm.ask("  Push to GitHub Pages?", default=True)

    def deployment_skipped(self) -> None:
        self._logger.info("Deployment skipped by user.")

    def deployment_failed(self, error: str) -> None:
        console.print()
        console.print(f"[red bold]Deployment failed:[/red bold] {error}")

    def deployment_success(self, url: str) -> None:
        console.print()
        console.print(Panel(
            f"[bold green]✔ Deployed successfully![/bold green]\n\n"
            f"[dim]Live at:[/dim] [blue underline]{url}[/blue underline]\n"
            f"[dim](GitHub Pages may take ~30 seconds to update)[/dim]",
            style="green",
            expand=False,
        ))

    def cancelled(self) -> None:
        console.print("\n[yellow]Cancelled.[/yellow]")

    # ── Summary ───────────────────────────────────────────────────────────────

    def show_summary(self, summary: dict) -> None:
        console.print()
        console.print(Rule("[bold]Run Summary[/bold]"))
        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column("Metric", style="dim", min_width=20)
        t.add_column("Value")

        for key, val in summary.items():
            t.add_row(key.replace("_", " ").title() + ":", str(val))

        console.print(t)
        console.print()


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    try:
        from core.container      import Container
        from core.orchestrator   import Orchestrator
        from core.workflow_manager import WorkflowManager
        from services.config_service import ConfigError
    except ImportError as exc:
        print(f"Import error: {exc}")
        print("Make sure you run: pip install -r agent/requirements.txt")
        sys.exit(1)

    try:
        container   = Container()
    except ConfigError as exc:
        print(f"\n✖ Configuration error:\n  {exc}\n")
        print("Edit agent/.env and fill in your API keys.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n✖ Startup error: {exc}")
        sys.exit(1)

    cli         = CLI(container.logger)
    orchestrator = Orchestrator(container)
    workflow    = WorkflowManager(orchestrator, cli, container)

    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
