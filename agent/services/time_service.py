"""
time_service.py — Centralised time and duration utilities.

All temporal logic in the system flows through this service.
No agent or service embeds datetime.now() or time.time() directly.
"""

import time
from datetime import datetime


class TimeService:
    """
    Lightweight service for timestamps and elapsed-time calculations.
    Inject this wherever time is needed to keep temporal logic testable
    and consistent across the whole system.
    """

    def now_iso(self) -> str:
        """Return current local time as ISO-8601 string (no timezone suffix).

        Example: '2026-07-09T18:47:00'
        """
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def now_unix(self) -> float:
        """Return current UNIX timestamp (seconds since epoch)."""
        return time.time()

    def elapsed(self, start: float) -> str:
        """Return human-readable duration since *start* (from now_unix()).

        Examples: '3.2s', '1m 12.5s'
        """
        delta = time.time() - start
        if delta < 60:
            return f"{delta:.1f}s"
        minutes = int(delta // 60)
        seconds = delta % 60
        return f"{minutes}m {seconds:.1f}s"

    def date_str(self) -> str:
        """Return today's date as 'YYYY-MM-DD' (used for log filenames)."""
        return datetime.now().strftime("%Y-%m-%d")

    def year(self) -> int:
        """Return the current calendar year as an integer."""
        return datetime.now().year
