"""
recovery_service.py — Backup and rollback for file operations.

Transaction protocol:
    1. recovery.backup([...files])   → creates timestamped backup
    2. patcher edits files
    3. validation fails  → recovery.restore() → files returned to backup state
    4. deployment succeeds → recovery.archive() → backup moved to archive

Backups stored in: agent/memory/backups/<timestamp>/
Only the last 10 backups are retained.
"""

import shutil
from pathlib import Path


class RecoveryService:
    """
    Backup-and-restore stack for safe file patching.

    All destructive file operations must call backup() before proceeding.
    On any failure, call restore() to return files to their pre-patch state.
    """

    MAX_BACKUPS = 10

    def __init__(self, config, logger, time_service):
        self._config = config
        self._logger = logger
        self._time   = time_service
        self._backup_root = Path(__file__).parent.parent / "memory" / "backups"
        self._backup_root.mkdir(parents=True, exist_ok=True)
        self._active_backup: Path | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def backup(self, file_paths: list[str | Path]) -> Path:
        """
        Copy each file to a timestamped backup directory.

        Args:
            file_paths: Portfolio-relative or absolute paths to back up.

        Returns:
            Path to the created backup directory.
        """
        ts = self._time.now_iso().replace(":", "-").replace("T", "_")
        backup_dir = self._backup_root / ts
        backup_dir.mkdir(parents=True, exist_ok=True)

        portfolio_root = self._config.portfolio_root
        for fp in file_paths:
            src = Path(fp) if Path(fp).is_absolute() else portfolio_root / fp
            if src.exists():
                shutil.copy2(src, backup_dir / src.name)
                self._logger.info(f"Backed up: {src.name}")
            else:
                self._logger.warning(f"Backup skipped (not found): {src}")

        self._active_backup = backup_dir
        self._prune_old_backups()
        return backup_dir

    def restore(self) -> bool:
        """
        Restore all files from the active backup.

        Returns True on success, False if no backup exists.
        """
        if not self._active_backup or not self._active_backup.exists():
            self._logger.error("No active backup to restore from.")
            return False

        portfolio_root = self._config.portfolio_root
        restored = []
        for src in self._active_backup.iterdir():
            dst = portfolio_root / src.name
            shutil.copy2(src, dst)
            restored.append(src.name)

        self._logger.success(f"Restored {len(restored)} file(s) from backup.")
        return True

    def archive(self, commit_hash: str = "") -> None:
        """
        Mark the active backup as successfully deployed.
        Renames the backup directory to include the commit hash.
        """
        if not self._active_backup:
            return
        label = f"{self._active_backup.name}_deployed_{commit_hash[:7]}" \
                if commit_hash else f"{self._active_backup.name}_deployed"
        archived = self._active_backup.parent / label
        self._active_backup.rename(archived)
        self._active_backup = None
        self._logger.info(f"Backup archived as: {archived.name}")

    def has_active_backup(self) -> bool:
        return self._active_backup is not None and self._active_backup.exists()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _prune_old_backups(self) -> None:
        """Keep only the last MAX_BACKUPS backup directories."""
        dirs = sorted(
            [d for d in self._backup_root.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
        )
        while len(dirs) > self.MAX_BACKUPS:
            oldest = dirs.pop(0)
            shutil.rmtree(oldest, ignore_errors=True)
