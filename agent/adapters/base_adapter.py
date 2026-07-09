"""
base_adapter.py — Abstract interface for all deployment adapters.

Rules:
    - All deployment adapters MUST extend BaseDeploymentAdapter.
    - Deployment Service loads the correct adapter from .env (DEPLOYMENT_ADAPTER).
    - Adding a new deployment target never requires changes to Workflow Manager,
      Orchestrator, or any Agent.
    - The adapter is responsible for prepare → diff → deploy → rollback.

Extension point:
    To add a new deployment target:
    1. Create a new file in agent/adapters/
    2. Subclass BaseDeploymentAdapter
    3. Implement all abstract methods
    4. Register the adapter name in DeploymentService._ADAPTERS
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeploymentResult:
    """Result returned by BaseDeploymentAdapter.deploy()."""
    success:     bool
    commit_hash: str = ""
    url:         str = ""
    message:     str = ""
    error:       str = ""


class BaseDeploymentAdapter(ABC):
    """
    Abstract base for all deployment adapters.

    Subclasses implement the 5 lifecycle methods below.
    DeploymentService calls them in order: prepare → diff → deploy.
    rollback() is called on failure. status() can be called any time.
    """

    @abstractmethod
    def prepare(self, files: list[str]) -> bool:
        """
        Stage files for deployment (e.g. git add).

        Args:
            files: List of file paths relative to portfolio root.

        Returns:
            True if staging succeeded, False otherwise.
        """

    @abstractmethod
    def diff(self) -> str:
        """
        Return a human-readable diff of staged changes.

        Returns:
            String representation of changes (shown to user before push).
        """

    @abstractmethod
    def deploy(self, message: str) -> DeploymentResult:
        """
        Execute the deployment (e.g. git commit + push).

        Args:
            message: Commit message or deployment description.

        Returns:
            DeploymentResult with success status, commit hash, live URL.
        """

    @abstractmethod
    def rollback(self, checkpoint: str = "") -> bool:
        """
        Revert to a previous deployment state.

        Args:
            checkpoint: Identifier for the state to revert to (e.g. commit hash).

        Returns:
            True if rollback succeeded, False otherwise.
        """

    @abstractmethod
    def status(self) -> str:
        """
        Return a human-readable summary of the current deployment state.
        """
