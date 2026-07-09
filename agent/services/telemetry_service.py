"""
telemetry_service.py — Per-run metrics, LLM usage tracking, and run logs.

Telemetry is written to:
    agent/memory/telemetry.db  — SQLite (persistent, queryable)
    agent/memory/logs/<date>.jsonl — structured daily log (human-readable)

Rules:
    - Telemetry must never crash the pipeline. All writes are fire-and-forget.
    - start_run() must be called first; finish_run() must be called last.
    - Individual LLM calls increment counters via record_llm_call().
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class RunMetrics:
    """In-memory metrics for a single agent run."""
    run_id:                str  = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at:            str  = ""
    finished_at:           str  = ""
    workflow_status:       str  = "running"
    project_key:           str  = ""
    provider:              str  = ""
    model:                 str  = ""
    llm_requests:          int  = 0
    total_tokens:          int  = 0
    prompt_tokens:         int  = 0
    completion_tokens:     int  = 0
    validation_failures:   int  = 0
    reflection_rejections: int  = 0
    retries:               int  = 0
    deployment_duration_s: float = 0.0
    total_duration_s:      float = 0.0
    error_message:         str  = ""


class TelemetryService:
    """
    Tracks all metrics for an agent run and persists them after completion.
    """

    def __init__(self, config, time_service, db_service):
        self._config = config
        self._time = time_service
        self._db = db_service
        self._enabled = config.telemetry_enabled
        self._current: RunMetrics | None = None
        self._run_start: float = 0.0

    # ── Run Lifecycle ─────────────────────────────────────────────────────────

    def start_run(self, project_key: str = "") -> str:
        """Begin a new run. Returns the run_id."""
        self._current = RunMetrics(
            started_at=self._time.now_iso(),
            project_key=project_key,
            provider=self._config.provider,
            model=self._config.model,
        )
        self._run_start = self._time.now_unix()
        return self._current.run_id

    def finish_run(self, status: str, error: str = "") -> None:
        """Finalise and persist the current run."""
        if not self._current:
            return
        self._current.finished_at = self._time.now_iso()
        self._current.workflow_status = status
        self._current.error_message = error
        self._current.total_duration_s = round(
            self._time.now_unix() - self._run_start, 2
        )
        self._persist()

    def set_deployment_duration(self, seconds: float) -> None:
        if self._current:
            self._current.deployment_duration_s = round(seconds, 2)

    # ── Increment Counters ────────────────────────────────────────────────────

    def record_llm_call(self, prompt_tokens: int = 0,
                         completion_tokens: int = 0) -> None:
        if not self._current:
            return
        self._current.llm_requests += 1
        self._current.prompt_tokens += prompt_tokens
        self._current.completion_tokens += completion_tokens
        self._current.total_tokens += prompt_tokens + completion_tokens

    def record_validation_failure(self) -> None:
        if self._current:
            self._current.validation_failures += 1

    def record_reflection_rejection(self) -> None:
        if self._current:
            self._current.reflection_rejections += 1

    def record_retry(self) -> None:
        if self._current:
            self._current.retries += 1

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def run_id(self) -> str:
        return self._current.run_id if self._current else ""

    def summary(self) -> dict:
        if not self._current:
            return {}
        m = self._current
        return {
            "run_id":          m.run_id,
            "status":          m.workflow_status,
            "project":         m.project_key,
            "provider":        m.provider,
            "model":           m.model,
            "llm_calls":       m.llm_requests,
            "total_tokens":    m.total_tokens,
            "duration":        self._time.elapsed(self._run_start),
            "deploy_duration": f"{m.deployment_duration_s:.1f}s",
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist(self) -> None:
        if not self._enabled or not self._current:
            return
        try:
            import dataclasses
            self._db.insert_run(dataclasses.asdict(self._current))
        except Exception:
            pass  # telemetry must never crash the pipeline
