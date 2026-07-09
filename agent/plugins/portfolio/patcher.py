"""
patcher.py — Edits portfolio files on behalf of the Portfolio Plugin.

Targets:
    projects.json   → append new project entry (canonical source of truth)
    script.js       → update PROJECT_DATA inline block (works on file:// and HTTP)
    index.html      → insert card HTML before anchor comment (legacy structure support)

Rules:
    - Always reads fresh file content before patching (never uses stale state).
    - projects.json is the canonical data source. script.js is kept in sync.
    - The PROJECT_DATA block in script.js is bounded by AGENT_DATA_START / AGENT_DATA_END.
    - RecoveryService must have created a backup BEFORE patch() is called.
"""

import json
import re
from pathlib import Path

from plugins.portfolio.renderer import PortfolioRenderer, CARD_ANCHOR

# Markers in script.js that bound the editable PROJECT_DATA block
_JS_START_MARKER = "// AGENT_DATA_START"
_JS_END_MARKER   = "// AGENT_DATA_END"


class PortfolioPatcher:
    """
    Applies patches to projects.json and index.html.
    """

    def __init__(self, config, logger):
        self._config   = config
        self._logger   = logger
        self._renderer = PortfolioRenderer()
        self._root     = config.portfolio_root

    @property
    def projects_json_path(self) -> Path:
        return self._root / "projects.json"

    @property
    def index_html_path(self) -> Path:
        return self._root / "index.html"

    def patch(self, project: dict) -> dict:
        """
        Apply all patches for a new project.

        Args:
            project: Full project data dict from Content Agent.

        Returns:
            dict with keys: projects_json_patched, script_js_patched,
                            index_html_patched, card_html (the inserted fragment)
        """
        json_ok   = self._patch_projects_json(project)
        js_ok     = self._patch_script_js()      # rebuild full PROJECT_DATA from projects.json
        card_html = self._renderer.render_card(project)
        html_ok   = self._patch_index_html(card_html)

        return {
            "projects_json_patched": json_ok,
            "script_js_patched":     js_ok,
            "index_html_patched":    html_ok,
            "card_html":             card_html,
        }

    # ── script.js (PROJECT_DATA inline block) ────────────────────────────────

    def _patch_script_js(self) -> bool:
        """
        Rebuild the PROJECT_DATA inline object in script.js from projects.json.

        Replaces everything between // AGENT_DATA_START and // AGENT_DATA_END
        with a fresh const PROJECT_DATA = { ... } built from the current projects.json.
        This keeps the site working when opened via file:// (no server needed).
        """
        js_path = self._root / "script.js"
        if not js_path.exists():
            self._logger.error("script.js not found. Skipping inline data sync.")
            return False

        try:
            # Read current projects.json
            data = json.loads(self.projects_json_path.read_text(encoding="utf-8"))
            projects = data.get("projects", {})

            # Build JS object literal
            js_entries = []
            for key, p in projects.items():
                images_js = json.dumps(p.get("images", []), ensure_ascii=False)
                tags_js   = json.dumps(p.get("tech_tags", []), ensure_ascii=False)
                entry = (
                    f'    "{key}": {{\n'
                    f'        "title": {json.dumps(p.get("title",""), ensure_ascii=False)},\n'
                    f'        "short_desc": {json.dumps(p.get("short_desc",""), ensure_ascii=False)},\n'
                    f'        "full_desc": {json.dumps(p.get("full_desc",""), ensure_ascii=False)},\n'
                    f'        "github": {json.dumps(p.get("github",""), ensure_ascii=False)},\n'
                    f'        "cover": {json.dumps(p.get("cover",""), ensure_ascii=False)},\n'
                    f'        "images": {images_js},\n'
                    f'        "tech_tags": {tags_js},\n'
                    f'        "category": {json.dumps(p.get("category",""), ensure_ascii=False)},\n'
                    f'        "year": {p.get("year", 0)}\n'
                    f'    }}'
                )
                js_entries.append(entry)

            new_block = (
                f"{_JS_START_MARKER}\n"
                f"const PROJECT_DATA = {{\n"
                + ",\n".join(js_entries) + "\n"
                f"}};\n"
                f"{_JS_END_MARKER}"
            )

            content = js_path.read_text(encoding="utf-8")
            # Replace between markers (inclusive)
            pattern = re.compile(
                re.escape(_JS_START_MARKER) + r".*?" + re.escape(_JS_END_MARKER),
                re.DOTALL,
            )
            if not pattern.search(content):
                self._logger.error(
                    "AGENT_DATA_START/END markers not found in script.js. "
                    "Cannot sync inline data."
                )
                return False

            new_content = pattern.sub(new_block, content, count=1)
            js_path.write_text(new_content, encoding="utf-8")
            self._logger.success(
                f"script.js: PROJECT_DATA synced ({len(projects)} projects)."
            )
            return True

        except Exception as exc:
            self._logger.error(f"Failed to patch script.js: {exc}")
            return False

    # ── projects.json ─────────────────────────────────────────────────────────

    def _patch_projects_json(self, project: dict) -> bool:
        """Append the new project entry to projects.json."""
        path = self.projects_json_path
        if not path.exists():
            self._logger.error(f"projects.json not found at: {path}")
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            projects = data.get("projects", {})

            key = project["key"]
            if key in projects:
                self._logger.warning(
                    f"Key '{key}' already in projects.json. Overwriting."
                )

            # Build the JSON entry (presentation fields only)
            projects[key] = {
                "title":      project.get("title", ""),
                "short_desc": project.get("short_desc", ""),
                "full_desc":  project.get("full_desc", ""),
                "github":     project.get("github_url", ""),
                "cover":      project.get("cover_image", ""),
                "images":     project.get("images", []),
                "tech_tags":  project.get("tech_tags", []),
                "category":   project.get("category", ""),
                "year":       project.get("year", 0),
            }

            data["projects"] = projects
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._logger.success(f"projects.json: added key '{key}'")
            return True

        except Exception as exc:
            self._logger.error(f"Failed to patch projects.json: {exc}")
            return False

    # ── index.html ────────────────────────────────────────────────────────────

    def _patch_index_html(self, card_html: str) -> bool:
        """
        Insert the card HTML immediately before the anchor comment.
        Uses string replacement on the anchor — no regex, no DOM manipulation.
        The anchor itself remains in place so future insertions work correctly.
        """
        path = self.index_html_path
        if not path.exists():
            self._logger.error(f"index.html not found at: {path}")
            return False

        try:
            # Ensure anchor exists (inject if missing)
            self._renderer.inject_anchor_if_missing(path)

            content = path.read_text(encoding="utf-8")
            if CARD_ANCHOR not in content:
                self._logger.error(
                    "Anchor comment not found in index.html after injection attempt."
                )
                return False

            # Insert card HTML before the anchor (anchor stays in place)
            new_content = content.replace(
                CARD_ANCHOR,
                card_html + "\n        " + CARD_ANCHOR,
                1,   # only first occurrence
            )
            path.write_text(new_content, encoding="utf-8")
            self._logger.success("index.html: project card inserted.")
            return True

        except Exception as exc:
            self._logger.error(f"Failed to patch index.html: {exc}")
            return False

    def read_projects_json(self) -> dict:
        """Read and return the current projects.json contents."""
        path = self.projects_json_path
        if not path.exists():
            return {"_meta": {}, "projects": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    def generate_projects_json_from_db(self, db_projects: list[dict],
                                        time_service) -> None:
        """
        Regenerate projects.json entirely from database records.
        Called on first run to migrate from hardcoded script.js data.
        """
        projects_out = {}
        for p in db_projects:
            projects_out[p["key"]] = {
                "title":      p.get("title", ""),
                "short_desc": p.get("short_desc", ""),
                "full_desc":  p.get("full_desc", ""),
                "github":     p.get("github_url", ""),
                "cover":      p.get("cover_image", ""),
                "images":     p.get("images", []),
                "tech_tags":  p.get("tech_tags", []),
                "category":   p.get("category", ""),
                "year":       p.get("year", 0),
            }

        data = {
            "_meta": {
                "generated_at":  time_service.now_iso(),
                "generated_by":  "portfolio-agent",
                "source":        "agent/memory/projects.db",
                "version":       "1.0",
            },
            "projects": projects_out,
        }
        self.projects_json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._logger.success(
            f"projects.json regenerated ({len(projects_out)} projects)."
        )
