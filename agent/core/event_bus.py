"""
event_bus.py — Event bus for inter-component communication.

Phase 1 (current): synchronous, in-process message forwarding.
    Subscribers are plain callables stored in a dict.
    emit() calls all matching handlers immediately.

Phase 2 (future): replace _dispatch() with an async queue.
    Zero changes required to callers — the public API is identical.

Usage:
    event_bus.subscribe(Events.DEPLOYMENT_SUCCESS, my_handler)
    event_bus.emit(Events.DEPLOYMENT_SUCCESS, {"commit": "abc123"})
"""

from __future__ import annotations

from typing import Callable
from collections import defaultdict


class EventBus:
    """
    Phase-1 synchronous event bus.

    Extension point: to add async support in Phase 2, replace _dispatch()
    with an asyncio.Queue and add a run_forever() coroutine. All emit()
    and subscribe() call-sites remain unchanged.
    """

    def __init__(self, logger=None):
        # handlers: event_name → list of callables
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._logger = logger
        # History kept in memory for debugging (last 100 events)
        self._history: list[dict] = []

    def subscribe(self, event: str, handler: Callable) -> None:
        """Register a handler for an event type.

        Multiple handlers per event are supported.
        Handlers are called in registration order.
        """
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Remove a previously registered handler."""
        if handler in self._handlers[event]:
            self._handlers[event].remove(handler)

    def emit(self, event: str, payload: dict | None = None) -> None:
        """Broadcast an event to all registered subscribers.

        Phase 1: synchronous — all handlers run before emit() returns.
        Phase 2 extension point: make this enqueue to an async queue.
        """
        payload = payload or {}
        self._record(event, payload)

        handlers = self._handlers.get(event, [])
        for handler in handlers:
            try:
                handler(event, payload)
            except Exception as exc:
                if self._logger:
                    self._logger.warning(
                        f"EventBus: handler raised for '{event}': {exc}"
                    )

    def history(self, n: int = 20) -> list[dict]:
        """Return the last *n* emitted events (for debugging)."""
        return self._history[-n:]

    def clear_handlers(self) -> None:
        """Remove all registered handlers (useful in tests)."""
        self._handlers.clear()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _record(self, event: str, payload: dict) -> None:
        self._history.append({"event": event, "payload": payload})
        if len(self._history) > 100:
            self._history.pop(0)
