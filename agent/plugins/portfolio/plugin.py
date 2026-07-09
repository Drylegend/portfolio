"""
plugin.py — Portfolio plugin (the only fully implemented plugin).

Implements BasePlugin for the portfolio website automation workflow.
Coordinates PortfolioPatcher and PortfolioRenderer.
"""

from plugins.base_plugin import BasePlugin, ValidationResult
from plugins.portfolio.patcher import PortfolioPatcher
from plugins.portfolio.renderer import PortfolioRenderer


class PortfolioPlugin(BasePlugin):
    """
    Fully implemented plugin for portfolio website automation.

    Responsibilities:
    - Insert new project cards into index.html
    - Append new project entries to projects.json
    - Validate patches before returning to Orchestrator
    """

    name    = "Portfolio"
    version = "1.0.0"

    def __init__(self):
        self._patcher:  PortfolioPatcher  | None = None
        self._renderer: PortfolioRenderer | None = None
        self._config  = None
        self._logger  = None

    def initialize(self, container) -> None:
        self._config   = container.config
        self._logger   = container.logger
        self._patcher  = PortfolioPatcher(container.config, container.logger)
        self._renderer = PortfolioRenderer()

        # Ensure anchor comment exists in index.html
        try:
            added = self._renderer.inject_anchor_if_missing(
                self._patcher.index_html_path
            )
            if added:
                self._logger.info("Portfolio: injected anchor comment into index.html")
        except Exception as exc:
            raise RuntimeError(
                f"Portfolio plugin failed to initialise: {exc}"
            ) from exc

    def analyze(self, context: dict) -> dict:
        """Return a snapshot of the current projects.json state."""
        data = self._patcher.read_projects_json()
        return {
            "project_count": len(data.get("projects", {})),
            "existing_keys": list(data.get("projects", {}).keys()),
        }

    def execute(self, payload: dict) -> dict:
        """
        Patch projects.json and index.html with the new project.

        Args:
            payload: Full project data dict from Content Agent.

        Returns:
            Patch result dict.
        """
        self._logger.agent("PortfolioPlugin", f"Patching for key: {payload.get('key')}")
        result = self._patcher.patch(payload)
        return result

    def validate(self, result: dict) -> ValidationResult:
        """Verify that the patch was applied correctly."""
        errors = []

        if not result.get("projects_json_patched"):
            errors.append("projects.json was not patched successfully.")

        if not result.get("index_html_patched"):
            errors.append("index.html was not patched successfully.")

        if not result.get("card_html"):
            errors.append("No card HTML was generated.")

        return ValidationResult(passed=len(errors) == 0, errors=errors)

    def cleanup(self, success: bool) -> None:
        """No persistent resources to clean up for this plugin."""
        pass

    def generate_from_db(self, db_projects: list[dict], time_service) -> None:
        """Regenerate projects.json entirely from database (used on first run)."""
        self._patcher.generate_projects_json_from_db(db_projects, time_service)
