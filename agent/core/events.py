"""
events.py — Event type constants for the Portfolio AI Agent Event Bus.

Phase 1: EventBus forwards messages synchronously through the Orchestrator.
Phase 2: Replace EventBus internals with async queues. Zero changes to callers.

Usage:
    from core.events import Events
    event_bus.emit(Events.IMAGE_PROCESSED, {"filename": "cover.jpg"})
"""


class Events:
    # ── Portfolio Lifecycle ───────────────────────────────────────────────────
    PORTFOLIO_LOADED        = "PORTFOLIO_LOADED"
    NEW_PROJECT_DETECTED    = "NEW_PROJECT_DETECTED"
    PROJECT_ADDED           = "PROJECT_ADDED"
    PROJECT_UPDATED         = "PROJECT_UPDATED"

    # ── Image Pipeline ────────────────────────────────────────────────────────
    IMAGE_SCANNED           = "IMAGE_SCANNED"
    IMAGE_PROCESSED         = "IMAGE_PROCESSED"
    IMAGE_DUPLICATE_FOUND   = "IMAGE_DUPLICATE_FOUND"
    IMAGE_AMBIGUOUS         = "IMAGE_AMBIGUOUS"

    # ── Content Pipeline ──────────────────────────────────────────────────────
    CONTENT_EXTRACTED       = "CONTENT_EXTRACTED"
    REFLECTION_ACCEPTED     = "REFLECTION_ACCEPTED"
    REFLECTION_REJECTED     = "REFLECTION_REJECTED"

    # ── Validation ────────────────────────────────────────────────────────────
    VALIDATION_PASSED       = "VALIDATION_PASSED"
    VALIDATION_FAILED       = "VALIDATION_FAILED"

    # ── Patching ──────────────────────────────────────────────────────────────
    PATCH_APPLIED           = "PATCH_APPLIED"
    PATCH_FAILED            = "PATCH_FAILED"

    # ── Testing ───────────────────────────────────────────────────────────────
    SMOKE_TEST_PASSED       = "SMOKE_TEST_PASSED"
    SMOKE_TEST_FAILED       = "SMOKE_TEST_FAILED"

    # ── Deployment ────────────────────────────────────────────────────────────
    DEPLOYMENT_STARTED      = "DEPLOYMENT_STARTED"
    DEPLOYMENT_SUCCESS      = "DEPLOYMENT_SUCCESS"
    DEPLOYMENT_FAILED       = "DEPLOYMENT_FAILED"

    # ── Recovery ──────────────────────────────────────────────────────────────
    BACKUP_CREATED          = "BACKUP_CREATED"
    ROLLBACK_TRIGGERED      = "ROLLBACK_TRIGGERED"
    ROLLBACK_SUCCESS        = "ROLLBACK_SUCCESS"

    # ── Memory ────────────────────────────────────────────────────────────────
    MEMORY_UPDATED          = "MEMORY_UPDATED"
    MEMORY_SEEDED           = "MEMORY_SEEDED"
