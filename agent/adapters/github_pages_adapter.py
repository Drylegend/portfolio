"""
github_pages_adapter.py — GitHub Pages deployment via git CLI.

Implements BaseDeploymentAdapter for the GitHub Pages target.

Pipeline:
    prepare()  → git add <files>
    diff()     → git diff --cached (shown to user for review)
    deploy()   → git commit -m <message> + git push origin <branch>
    rollback() → git revert HEAD --no-commit + git push (safe, no force push)
    status()   → git status + git log -1

Safety:
    - Never force-pushes.
    - Always shows diff to user before deploy() is called.
    - deploy() is only called after explicit user confirmation in CLI.
"""

import subprocess
from pathlib import Path

from adapters.base_adapter import BaseDeploymentAdapter, DeploymentResult


class GitHubPagesAdapter(BaseDeploymentAdapter):
    """
    Deployment adapter for GitHub Pages via git CLI.
    """

    def __init__(self, config, logger):
        self._config = config
        self._logger = logger
        self._root   = str(config.portfolio_root)
        self._branch = config.github_branch
        self._url    = config.github_pages_url

    def prepare(self, files: list[str]) -> bool:
        """Stage files with git add."""
        if not files:
            self._logger.warning("No files provided to git add.")
            return False

        result = self._run(["git", "add"] + files)
        if result.returncode == 0:
            self._logger.success(f"Staged {len(files)} file(s) for commit.")
            return True
        self._logger.error(f"git add failed:\n{result.stderr}")
        return False

    def diff(self) -> str:
        """Return staged diff as a string."""
        result = self._run(["git", "diff", "--cached", "--stat"])
        if result.returncode != 0:
            return "(could not retrieve diff)"
        diff_text = result.stdout.strip()
        return diff_text if diff_text else "(no staged changes)"

    def deploy(self, message: str) -> DeploymentResult:
        """Commit and push to GitHub."""
        # Commit
        commit = self._run(["git", "commit", "-m", message])
        if commit.returncode != 0:
            err = commit.stderr.strip()
            if "nothing to commit" in err.lower():
                return DeploymentResult(
                    success=False,
                    error="Nothing to commit — portfolio may already be up to date."
                )
            self._logger.error(f"git commit failed:\n{err}")
            return DeploymentResult(success=False, error=err)

        # Get commit hash
        hash_result = self._run(["git", "rev-parse", "HEAD"])
        commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else ""

        # Push
        push = self._run(["git", "push", "origin", self._branch])
        if push.returncode != 0:
            err = push.stderr.strip()
            self._logger.error(f"git push failed:\n{err}")
            return DeploymentResult(
                success=False, commit_hash=commit_hash, error=err
            )

        self._logger.success(f"Pushed to {self._branch} ({commit_hash[:7]})")
        return DeploymentResult(
            success=True,
            commit_hash=commit_hash,
            url=self._url,
            message=message,
        )

    def rollback(self, checkpoint: str = "") -> bool:
        """
        Revert the last commit safely (no force push).
        Creates a new revert commit rather than rewriting history.
        """
        if checkpoint:
            result = self._run(["git", "revert", checkpoint, "--no-commit"])
        else:
            result = self._run(["git", "revert", "HEAD", "--no-commit"])

        if result.returncode != 0:
            self._logger.error(f"git revert failed:\n{result.stderr}")
            return False

        commit = self._run(["git", "commit", "-m", "revert: rollback previous deployment"])
        if commit.returncode != 0:
            self._logger.error(f"Revert commit failed:\n{commit.stderr}")
            return False

        push = self._run(["git", "push", "origin", self._branch])
        if push.returncode != 0:
            self._logger.error(f"Revert push failed:\n{push.stderr}")
            return False

        self._logger.success("Rollback deployed successfully.")
        return True

    def status(self) -> str:
        """Return git status + last commit summary."""
        status = self._run(["git", "status", "--short"])
        log    = self._run(["git", "log", "-1", "--oneline"])
        lines = []
        if log.returncode == 0:
            lines.append(f"Last commit: {log.stdout.strip()}")
        if status.returncode == 0:
            lines.append(f"Working tree: {status.stdout.strip() or 'clean'}")
        return "\n".join(lines)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=self._root,
            capture_output=True,
            text=True,
        )
