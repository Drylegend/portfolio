"""
base_plugin.py — Abstract plugin interface.

All plugins MUST extend BasePlugin and implement all 5 lifecycle methods.

Plugin contract:
    initialize()  → load config, check prerequisites, prepare state
    analyze()     → inspect current state, return analysis dict
    execute()     → perform the main action, return result dict
    validate()    → verify result is correct, return ValidationResult
    cleanup()     → close handles, archive backups, free resources

Only the Portfolio plugin has a real implementation.
All other plugins are documented skeletons.

Extension point:
    To add a new plugin module (e.g. resume, blog):
    1. Create agent/plugins/<name>/
    2. Implement BasePlugin
    3. Register in Orchestrator plugin registry
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result returned by BasePlugin.validate()."""
    passed:  bool
    errors:  list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self):
        return self.passed


class BasePlugin(ABC):
    """
    Abstract base for all automation plugins.

    Each plugin targets a specific output (portfolio site, resume, blog, etc.)
    and implements the 5 lifecycle methods below.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name (e.g. 'Portfolio', 'Resume')."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version string (e.g. '1.0.0')."""

    @abstractmethod
    def initialize(self, container) -> None:
        """
        Load plugin-specific config and verify prerequisites.

        Called once at startup before any other method.
        Raise RuntimeError if prerequisites are not met.

        Args:
            container: The DI Container exposing all services.
        """

    @abstractmethod
    def analyze(self, context: dict) -> dict:
        """
        Inspect the current state relevant to this plugin.

        Args:
            context: Shared context dict from Orchestrator.

        Returns:
            Analysis dict (plugin-specific structure).
        """

    @abstractmethod
    def execute(self, payload: dict) -> dict:
        """
        Perform the main plugin action.

        Args:
            payload: Structured data from Content Agent + Image Agent.

        Returns:
            Result dict describing what was changed.
        """

    @abstractmethod
    def validate(self, result: dict) -> ValidationResult:
        """
        Verify the result of execute() is correct.

        Args:
            result: The dict returned by execute().

        Returns:
            ValidationResult with passed=True/False and any errors.
        """

    @abstractmethod
    def cleanup(self, success: bool) -> None:
        """
        Post-run cleanup.

        Args:
            success: True if the workflow completed successfully.
        """
