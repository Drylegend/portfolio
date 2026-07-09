"""
memory_agent.py — Portfolio structure analysis and database seeding.

Responsibilities:
    - On first run: parse index.html with BeautifulSoup4 to extract existing
      project structure, then seed projects.db and image_index.db.
    - On subsequent runs: load portfolio state directly from projects.db.
    - Maintain portfolio_snapshot.json as a lightweight read-only reference.
    - Never parse HTML with regex or manual string operations.

Rules:
    - This agent uses the LLM ONLY for ambiguous HTML structure interpretation.
    - Standard portfolio structure is parsed with BeautifulSoup4 only.
    - Database is always the source of truth. HTML is only read, never authoritative.
"""

import json
import hashlib
from pathlib import Path


class MemoryAgent:
    """
    AI agent responsible for portfolio structure analysis and memory management.

    On first run, it bootstraps the SQLite databases from the current files.
    On all subsequent runs, it reads directly from the databases.
    """

    def __init__(self, llm, db, logger, config, time_service):
        self._llm    = llm
        self._db     = db
        self._logger = logger
        self._config = config
        self._time   = time_service
        self._root   = config.portfolio_root
        self._snapshot_path = (
            Path(__file__).parent.parent / "memory" / "portfolio_snapshot.json"
        )

    def load(self) -> dict:
        """
        Load portfolio state. Seeds from files on first run.

        Returns:
            dict with keys: projects (list), is_first_run (bool)
        """
        known = self._db.get_all_projects()

        if not known:
            self._logger.agent("MemoryAgent", "First run detected — seeding database from files.")
            self._seed_from_files()
            known = self._db.get_all_projects()
            is_first_run = True
        else:
            is_first_run = False

        self._logger.agent(
            "MemoryAgent",
            f"Portfolio state loaded: {len(known)} project(s) known."
        )

        return {
            "projects":     known,
            "known_keys":   {p["key"] for p in known},
            "is_first_run": is_first_run,
        }

    def update(self, project: dict, commit_hash: str, run_id: str) -> None:
        """
        Persist a newly added project to all databases.
        Called ONLY after confirmed deployment.

        Args:
            project:     Full project data dict.
            commit_hash: Git commit hash from DeploymentResult.
            run_id:      Telemetry run ID.
        """
        now = self._time.now_iso()

        # Snapshot existing project for history
        existing = self._db.get_project(project["key"])

        # Insert or update project
        db_row = {
            "key":             project["key"],
            "title":           project.get("title", ""),
            "short_desc":      project.get("short_desc", ""),
            "full_desc":       project.get("full_desc", ""),
            "github_url":      project.get("github_url", ""),
            "cover_image":     project.get("cover_image", ""),
            "images":          json.dumps(project.get("images", [])),
            "tech_tags":       json.dumps(project.get("tech_tags", [])),
            "frameworks":      json.dumps(project.get("frameworks", [])),
            "languages":       json.dumps(project.get("languages", [])),
            "category":        project.get("category", ""),
            "business_domain": project.get("business_domain", ""),
            "algorithms":      json.dumps(project.get("algorithms", [])),
            "datasets":        json.dumps(project.get("datasets", [])),
            "difficulty":      project.get("difficulty", ""),
            "project_purpose": project.get("project_purpose", ""),
            "keywords":        json.dumps(project.get("keywords", [])),
            "related_projects":json.dumps(project.get("related_projects", [])),
            "year":            project.get("year", self._time.year()),
            "created_at":      now,
            "updated_at":      now,
        }

        if existing:
            db_row.pop("created_at")
            self._db.update_project(project["key"], db_row)
        else:
            self._db.insert_project(db_row)

        # Insert image records
        for img_data in project.get("_image_records", []):
            self._db.insert_image(img_data)

        # Write history entry
        self._db.insert_history({
            "project_key": project["key"],
            "action":      "add" if not existing else "update",
            "snapshot":    json.dumps(existing) if existing else "{}",
            "commit_hash": commit_hash,
            "deployed_at": now,
            "agent_run_id": run_id,
        })

        # Update portfolio snapshot JSON
        self._update_snapshot()
        self._logger.agent("MemoryAgent", f"Memory updated for: {project['key']}")

    # ── First-Run Seeding ─────────────────────────────────────────────────────

    def _seed_from_files(self) -> None:
        """
        Parse projects.json (if it exists) to seed the database.
        Falls back to parsing index.html + script.js on legacy setup.
        """
        projects_json = self._root / "projects.json"

        if projects_json.exists():
            self._seed_from_projects_json(projects_json)
        else:
            self._logger.agent(
                "MemoryAgent",
                "projects.json not found. Will seed from index.html (legacy mode)."
            )
            self._seed_from_html()

        # Seed image_index.db from assets/ directory
        self._seed_images()

    def _seed_from_projects_json(self, path: Path) -> None:
        """Seed projects.db from the existing projects.json file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        projects = data.get("projects", {})
        now = self._time.now_iso()

        for key, p in projects.items():
            if not self._db.project_exists(key):
                self._db.insert_project({
                    "key":         key,
                    "title":       p.get("title", ""),
                    "short_desc":  p.get("short_desc", ""),
                    "full_desc":   p.get("full_desc", ""),
                    "github_url":  p.get("github", ""),
                    "cover_image": p.get("cover", ""),
                    "images":      json.dumps(p.get("images", [])),
                    "tech_tags":   json.dumps(p.get("tech_tags", [])),
                    "category":    p.get("category", ""),
                    "year":        p.get("year", 0),
                    "created_at":  now,
                    "updated_at":  now,
                })
        self._logger.agent(
            "MemoryAgent",
            f"Seeded {len(projects)} project(s) from projects.json."
        )

    def _seed_from_html(self) -> None:
        """
        Parse index.html with BeautifulSoup4 to extract project card data.
        Used only as a legacy fallback when projects.json doesn't exist yet.
        """
        from bs4 import BeautifulSoup

        html_path = self._root / "index.html"
        if not html_path.exists():
            self._logger.error("index.html not found. Cannot seed database.")
            return

        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")
        container = soup.find("div", class_="project-container")
        if not container:
            self._logger.error("No .project-container found in index.html.")
            return

        cards = container.find_all("div", class_="project-card")
        now = self._time.now_iso()

        for card in cards:
            btn = card.find("button")
            if not btn or "openModal(" not in btn.get("onclick", ""):
                continue

            # Extract project key from onclick="openModal('key')"
            onclick = btn.get("onclick", "")
            key = onclick.split("'")[1] if "'" in onclick else ""
            if not key:
                continue

            title_tag = card.find("h3")
            desc_tag  = card.find("p")
            img_tag   = card.find("img")

            title = title_tag.get_text(strip=True) if title_tag else key
            desc  = desc_tag.get_text(strip=True)  if desc_tag  else ""
            cover = img_tag.get("src", "")          if img_tag  else ""

            if not self._db.project_exists(key):
                self._db.insert_project({
                    "key":         key,
                    "title":       title,
                    "short_desc":  desc,
                    "cover_image": cover,
                    "created_at":  now,
                    "updated_at":  now,
                })

        self._logger.agent(
            "MemoryAgent",
            f"Seeded {len(cards)} project(s) from index.html."
        )

    def _seed_images(self) -> None:
        """Record all existing images in assets/ into image_index.db."""
        assets_dir = self._config.assets_dir
        if not assets_dir.exists():
            return

        known_filenames = self._db.get_all_image_filenames()
        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        now = self._time.now_iso()

        for f in assets_dir.iterdir():
            if f.suffix.lower() not in image_exts:
                continue
            if f.name in known_filenames:
                continue

            # Compute checksum
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            checksum = h.hexdigest()

            # Detect role from filename
            name_lower = f.stem.lower()
            role = "cover" if "cover" in name_lower else "gallery"

            # Try to match to an existing project key
            project_key = ""
            existing_keys = {p["key"] for p in self._db.get_all_projects()}
            for key in existing_keys:
                if name_lower.startswith(key):
                    project_key = key
                    break

            if not project_key:
                continue

            self._db.insert_image({
                "filename":    f.name,
                "filepath":    str(f),
                "project_key": project_key,
                "role":        role,
                "checksum":    checksum,
                "format":      f.suffix.lstrip(".").lower(),
                "added_at":    now,
            })

    def _update_snapshot(self) -> None:
        """Write portfolio_snapshot.json as a lightweight read-only reference."""
        projects = self._db.get_all_projects()
        snapshot = {
            "generated_at": self._time.now_iso(),
            "project_count": len(projects),
            "keys": [p["key"] for p in projects],
            "projects": {
                p["key"]: {
                    "title":      p.get("title", ""),
                    "cover":      p.get("cover_image", ""),
                    "updated_at": p.get("updated_at", ""),
                }
                for p in projects
            },
        }
        self._snapshot_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
