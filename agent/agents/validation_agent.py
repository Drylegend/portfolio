"""
validation_agent.py — Rule-based verification before and after file patching.

This agent performs deterministic checklist validation.
It does NOT call the LLM.

Two stages:
    pre_patch()   — validates project metadata BEFORE any file is modified
    post_patch()  — validates patched files AFTER modification

Rules:
    - Each check returns a specific, actionable error message on failure.
    - A single failed check causes the full validation to fail.
    - Post-patch uses BeautifulSoup4 to verify HTML integrity.
    - Rejection triggers Recovery Agent to restore files (post-patch only).
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ValidationReport:
    """Result of a full validation pass."""
    passed:   bool
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self):
        return self.passed


class ValidationAgent:
    """
    Rule-based validation agent. No LLM calls.

    pre_patch():  validates metadata and files before patching begins.
    post_patch(): validates the patched files for correctness and HTML integrity.
    """

    def __init__(self, db, logger, config):
        self._db     = db
        self._logger = logger
        self._config = config
        self._root   = config.portfolio_root

    def pre_patch(self, metadata) -> ValidationReport:
        """
        Validate project metadata before any files are modified.

        Args:
            metadata: ProjectMetadata from ContentAgent (after Reflection).

        Returns:
            ValidationReport — if not passed, pipeline must stop.
        """
        self._logger.agent("ValidationAgent", "Running pre-patch checks…")
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Duplicate key check
        if self._db.project_exists(metadata.key):
            errors.append(
                f"Project key '{metadata.key}' already exists in database. "
                "Are you trying to update an existing project? "
                "If so, use the update command (not yet implemented)."
            )

        # 2. Required fields
        if not metadata.title or len(metadata.title.strip()) < 3:
            errors.append("title is missing or too short (minimum 3 characters).")
        if not metadata.short_desc or len(metadata.short_desc.strip()) < 10:
            errors.append("short_desc is missing or too short (minimum 10 characters).")
        if not metadata.full_desc or len(metadata.full_desc.strip()) < 20:
            errors.append("full_desc is missing or too short (minimum 20 characters).")

        # 3. Cover image present and exists
        if not metadata.cover_image:
            errors.append("cover_image is missing. Every project must have a cover image.")
        else:
            cover_path = self._resolve_image_path(metadata.cover_image)
            if not cover_path.exists():
                errors.append(
                    f"Cover image not found on disk: {metadata.cover_image}"
                )

        # 4. All listed images exist on disk
        missing_images = []
        for img_path in metadata.images:
            resolved = self._resolve_image_path(img_path)
            if not resolved.exists():
                missing_images.append(img_path)
        if missing_images:
            errors.append(
                f"Gallery images not found on disk: {', '.join(missing_images)}"
            )

        # 5. GitHub URL format check (if provided)
        if metadata.github_url:
            if not self._is_valid_url(metadata.github_url):
                errors.append(
                    f"github_url does not look like a valid URL: {metadata.github_url}"
                )

        # 6. tech_tags not empty
        if not metadata.tech_tags:
            warnings.append("tech_tags is empty. Consider adding technology labels.")

        # 7. No duplicate image paths within the project
        all_images = metadata.images
        if len(all_images) != len(set(all_images)):
            errors.append("Duplicate image paths detected within the same project.")

        # 8. projects.json exists
        if not (self._root / "projects.json").exists():
            errors.append(
                "projects.json not found. Run Memory Agent seeding first."
            )

        # 9. index.html exists
        if not (self._root / "index.html").exists():
            errors.append("index.html not found in portfolio root.")

        report = ValidationReport(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
        self._log_report(report, "Pre-patch")
        return report

    def post_patch(self, project_key: str) -> ValidationReport:
        """
        Validate patched files after modification.
        Uses BeautifulSoup4 to check HTML integrity.

        Args:
            project_key: The key of the newly added project.

        Returns:
            ValidationReport — if not passed, Recovery Agent must restore.
        """
        self._logger.agent("ValidationAgent", "Running post-patch checks…")
        errors: list[str] = []
        warnings: list[str] = []

        # 1. projects.json is valid JSON
        pj_path = self._root / "projects.json"
        try:
            data = json.loads(pj_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"projects.json is not valid JSON after patching: {exc}")
            report = ValidationReport(passed=False, errors=errors)
            self._log_report(report, "Post-patch")
            return report

        # 2. New project key is present in projects.json
        if project_key not in data.get("projects", {}):
            errors.append(
                f"Project key '{project_key}' not found in projects.json after patching."
            )

        # 3. index.html parses without error (BeautifulSoup4)
        html_path = self._root / "index.html"
        try:
            from bs4 import BeautifulSoup
            html_content = html_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(html_content, "lxml")
        except Exception as exc:
            errors.append(f"index.html failed to parse with BeautifulSoup4: {exc}")
            report = ValidationReport(passed=False, errors=errors)
            self._log_report(report, "Post-patch")
            return report

        # 4. Anchor comment still present in index.html
        if "END PROJECT CARDS" not in html_content:
            warnings.append(
                "Anchor comment '<!-- END PROJECT CARDS -->' not found in index.html. "
                "Future insertions may fail."
            )

        # 5. A button with the correct openModal key exists in the HTML
        buttons = soup.find_all("button")
        modal_found = any(
            f"openModal('{project_key}')" in (btn.get("onclick") or "")
            for btn in buttons
        )
        if not modal_found:
            errors.append(
                f"No <button onclick=\"openModal('{project_key}')\"> found in index.html."
            )

        # 6. Cover image src exists as a tag
        imgs = soup.find_all("img")
        cover_in_html = any(project_key in (img.get("src") or "") for img in imgs)
        if not cover_in_html:
            warnings.append(
                f"No <img> with src containing '{project_key}' found in index.html. "
                "The card may not display the cover image correctly."
            )

        report = ValidationReport(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
        self._log_report(report, "Post-patch")
        return report

    # ── Internal ─────────────────────────────────────────────────────────────

    def _resolve_image_path(self, img_str: str) -> Path:
        """Resolve an image path (relative to portfolio root or absolute)."""
        p = Path(img_str)
        if p.is_absolute():
            return p
        return self._root / img_str

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}(?:\.\d{1,3}){3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$',
            re.IGNORECASE,
        )
        return bool(pattern.match(url))

    def _log_report(self, report: ValidationReport, stage: str) -> None:
        if report.passed:
            self._logger.agent("ValidationAgent", f"{stage} validation PASSED.")
        else:
            self._logger.error(f"{stage} validation FAILED.")
            for err in report.errors:
                self._logger.error(f"  ✖ {err}")
        for warn in report.warnings:
            self._logger.warning(f"  ⚠ {warn}")
