"""
database_service.py — SQLite interface for all agent databases.

Manages four databases:
    projects.db         — canonical project data (source of truth)
    image_index.db      — known images, checksums, dimensions
    project_history.db  — deployment history linked to git commits
    telemetry.db        — per-run metrics and LLM usage

Rules:
    - This service is the ONLY component that touches SQLite directly.
    - All other components call methods on this service.
    - projects.db is always written LAST (after confirmed deployment).
    - Schemas are created on first connection if they don't exist.
"""

import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Any


class DatabaseService:
    """
    Central SQLite interface. One service, four databases, clean separation.
    """

    def __init__(self, config, logger):
        self._logger = logger
        memory_dir = Path(__file__).parent.parent / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        self._paths = {
            "projects":  memory_dir / "projects.db",
            "images":    memory_dir / "image_index.db",
            "history":   memory_dir / "project_history.db",
            "telemetry": memory_dir / "telemetry.db",
        }

        self._init_schemas()

    # ── Schema Initialisation ────────────────────────────────────────────────

    def _init_schemas(self) -> None:
        with self._conn("projects") as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    key               TEXT PRIMARY KEY,
                    title             TEXT NOT NULL,
                    short_desc        TEXT,
                    full_desc         TEXT,
                    github_url        TEXT,
                    cover_image       TEXT,
                    images            TEXT,       -- JSON array
                    tech_tags         TEXT,       -- JSON array
                    frameworks        TEXT,       -- JSON array
                    languages         TEXT,       -- JSON array
                    category          TEXT,       -- ML | Web | Data | Tool | Research
                    business_domain   TEXT,
                    algorithms        TEXT,       -- JSON array
                    datasets          TEXT,       -- JSON array
                    difficulty        TEXT,       -- Beginner | Intermediate | Advanced
                    project_purpose   TEXT,
                    keywords          TEXT,       -- JSON array
                    related_projects  TEXT,       -- JSON array of keys
                    year              INTEGER,
                    embedding         BLOB,       -- Phase 2: float32 vector (NULL by default)
                    embedding_model   TEXT,
                    created_at        TEXT,
                    updated_at        TEXT
                )
            """)

        with self._conn("images") as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    filename      TEXT PRIMARY KEY,
                    filepath      TEXT NOT NULL,
                    project_key   TEXT,
                    role          TEXT,           -- cover | gallery
                    checksum      TEXT,           -- SHA-256
                    width         INTEGER,
                    height        INTEGER,
                    size_bytes    INTEGER,
                    processed     INTEGER DEFAULT 0,   -- 0=raw 1=optimised
                    format        TEXT,           -- jpg | webp | png
                    added_at      TEXT
                )
            """)

        with self._conn("history") as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_key   TEXT NOT NULL,
                    action        TEXT,           -- add | update | delete
                    snapshot      TEXT,           -- JSON of full project row before change
                    commit_hash   TEXT,
                    deployed_at   TEXT,
                    agent_run_id  TEXT
                )
            """)

        with self._conn("telemetry") as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id                TEXT PRIMARY KEY,
                    started_at            TEXT,
                    finished_at           TEXT,
                    workflow_status       TEXT,   -- success | failed | cancelled
                    project_key           TEXT,
                    provider              TEXT,
                    model                 TEXT,
                    llm_requests          INTEGER DEFAULT 0,
                    total_tokens          INTEGER DEFAULT 0,
                    prompt_tokens         INTEGER DEFAULT 0,
                    completion_tokens     INTEGER DEFAULT 0,
                    validation_failures   INTEGER DEFAULT 0,
                    reflection_rejections INTEGER DEFAULT 0,
                    retries               INTEGER DEFAULT 0,
                    deployment_duration_s REAL,
                    total_duration_s      REAL,
                    error_message         TEXT
                )
            """)

    # ── Project CRUD ─────────────────────────────────────────────────────────

    def get_all_projects(self) -> list[dict]:
        with self._conn("projects") as conn:
            rows = conn.execute("SELECT * FROM projects").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_project(self, key: str) -> dict | None:
        with self._conn("projects") as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE key = ?", (key,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def project_exists(self, key: str) -> bool:
        return self.get_project(key) is not None

    def insert_project(self, data: dict) -> bool:
        cols = list(data.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        values = [json.dumps(v) if isinstance(v, list) else v for v in data.values()]
        try:
            with self._conn("projects") as conn:
                conn.execute(
                    f"INSERT INTO projects ({col_names}) VALUES ({placeholders})",
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            self._logger.error(f"Insert project failed: {exc}")
            return False

    def update_project(self, key: str, updates: dict) -> bool:
        sets = ", ".join([f"{k} = ?" for k in updates])
        values = [json.dumps(v) if isinstance(v, list) else v for v in updates.values()]
        values.append(key)
        try:
            with self._conn("projects") as conn:
                conn.execute(
                    f"UPDATE projects SET {sets} WHERE key = ?", values
                )
            return True
        except Exception as exc:
            self._logger.error(f"Update project failed: {exc}")
            return False

    # ── Image CRUD ────────────────────────────────────────────────────────────

    def get_all_image_filenames(self) -> set[str]:
        with self._conn("images") as conn:
            rows = conn.execute("SELECT filename FROM images").fetchall()
        return {r[0] for r in rows}

    def image_exists_by_checksum(self, checksum: str) -> dict | None:
        with self._conn("images") as conn:
            row = conn.execute(
                "SELECT * FROM images WHERE checksum = ?", (checksum,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def insert_image(self, data: dict) -> bool:
        cols = list(data.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        try:
            with self._conn("images") as conn:
                conn.execute(
                    f"INSERT OR REPLACE INTO images ({col_names}) VALUES ({placeholders})",
                    list(data.values()),
                )
            return True
        except Exception as exc:
            self._logger.error(f"Insert image failed: {exc}")
            return False

    def mark_image_processed(self, filename: str, width: int, height: int,
                              size_bytes: int, fmt: str) -> None:
        with self._conn("images") as conn:
            conn.execute(
                """UPDATE images
                   SET processed=1, width=?, height=?, size_bytes=?, format=?
                   WHERE filename=?""",
                (width, height, size_bytes, fmt, filename),
            )

    # ── History ───────────────────────────────────────────────────────────────

    def insert_history(self, entry: dict) -> bool:
        cols = list(entry.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        try:
            with self._conn("history") as conn:
                conn.execute(
                    f"INSERT INTO history ({col_names}) VALUES ({placeholders})",
                    list(entry.values()),
                )
            return True
        except Exception as exc:
            self._logger.error(f"Insert history failed: {exc}")
            return False

    # ── Telemetry ────────────────────────────────────────────────────────────

    def insert_run(self, run_data: dict) -> bool:
        cols = list(run_data.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        try:
            with self._conn("telemetry") as conn:
                conn.execute(
                    f"INSERT INTO runs ({col_names}) VALUES ({placeholders})",
                    list(run_data.values()),
                )
            return True
        except Exception as exc:
            self._logger.error(f"Insert run failed: {exc}")
            return False

    def update_run(self, run_id: str, updates: dict) -> bool:
        sets = ", ".join([f"{k} = ?" for k in updates])
        values = list(updates.values()) + [run_id]
        try:
            with self._conn("telemetry") as conn:
                conn.execute(
                    f"UPDATE runs SET {sets} WHERE run_id = ?", values
                )
            return True
        except Exception as exc:
            self._logger.error(f"Update run failed: {exc}")
            return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self, db_name: str):
        path = self._paths[db_name]
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        # Deserialize JSON array columns
        for key in ("images", "tech_tags", "frameworks", "languages",
                    "algorithms", "datasets", "keywords", "related_projects"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = []
        return d
