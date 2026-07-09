"""
config_service.py — Loads and validates all configuration from .env.

Rules:
- Reads the .env file located in the agent/ directory.
- Fails fast with a clear error if required keys are missing.
- Exposes typed accessors so callers never parse strings themselves.
- Switching provider (gemini ↔ openrouter) requires only editing .env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


class ConfigService:
    """
    Single source of configuration for the entire agent system.
    Injected into every component that needs settings.
    """

    # Keys required regardless of provider
    _ALWAYS_REQUIRED = [
        "PROVIDER",
        "PORTFOLIO_ROOT",
        "ASSETS_DIR",
        "GITHUB_BRANCH",
    ]

    # Keys required per provider
    _PROVIDER_KEYS = {
        "gemini":      ["GEMINI_API_KEY",      "GEMINI_MODEL"],
        "openrouter":  ["OPENROUTER_API_KEY",  "OPENROUTER_MODEL"],
    }

    def __init__(self, env_path: str | Path | None = None):
        if env_path is None:
            # agent/.env lives one level above this file (agent/services/)
            env_path = Path(__file__).parent.parent / ".env"

        if not Path(env_path).exists():
            raise ConfigError(
                f".env file not found at: {env_path}\n"
                "Copy .env and fill in your API keys before running."
            )

        load_dotenv(env_path, override=True)
        self._data: dict[str, str] = dict(os.environ)
        self._validate()

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self) -> None:
        for key in self._ALWAYS_REQUIRED:
            if not self.get(key):
                raise ConfigError(f"Missing required config: {key}")

        provider = self.provider
        if provider not in self._PROVIDER_KEYS:
            raise ConfigError(
                f"PROVIDER must be 'gemini' or 'openrouter', got: '{provider}'"
            )
        for key in self._PROVIDER_KEYS[provider]:
            if not self.get(key):
                raise ConfigError(
                    f"Missing required config for provider '{provider}': {key}"
                )

    # ── Generic accessors ─────────────────────────────────────────────────────

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return raw string value from config, or *default*."""
        return self._data.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Return a boolean value from config (true/1/yes → True)."""
        val = self.get(key, str(default)).lower().strip()
        return val in ("true", "1", "yes")

    def get_int(self, key: str, default: int = 0) -> int:
        """Return an integer value from config."""
        try:
            return int(self.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    # ── Typed properties ─────────────────────────────────────────────────────

    @property
    def provider(self) -> str:
        return self.get("PROVIDER", "gemini").lower().strip()

    @property
    def model(self) -> str:
        if self.provider == "gemini":
            return self.get("GEMINI_MODEL", "gemini-2.0-flash")
        return self.get("OPENROUTER_MODEL", "")

    @property
    def api_key(self) -> str:
        if self.provider == "gemini":
            return self.get("GEMINI_API_KEY", "")
        return self.get("OPENROUTER_API_KEY", "")

    @property
    def openrouter_base_url(self) -> str:
        return self.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    @property
    def portfolio_root(self) -> Path:
        return Path(self.get("PORTFOLIO_ROOT", "."))

    @property
    def assets_dir(self) -> Path:
        return self.portfolio_root / self.get("ASSETS_DIR", "assets")

    @property
    def github_branch(self) -> str:
        return self.get("GITHUB_BRANCH", "main")

    @property
    def github_pages_url(self) -> str:
        return self.get("GITHUB_PAGES_URL", "")

    @property
    def deployment_adapter(self) -> str:
        return self.get("DEPLOYMENT_ADAPTER", "github_pages")

    @property
    def auto_push(self) -> bool:
        # Hard-coded safety: always returns False.
        # AUTO_PUSH in .env is intentionally ignored to prevent accidents.
        return False

    @property
    def require_smoke_test(self) -> bool:
        return self.get_bool("REQUIRE_SMOKE_TEST", True)

    @property
    def smoke_test_port(self) -> int:
        return self.get_int("SMOKE_TEST_PORT", 8765)

    @property
    def max_revision_attempts(self) -> int:
        return self.get_int("MAX_REVISION_ATTEMPTS", 3)

    @property
    def image_max_width(self) -> int:
        return self.get_int("IMAGE_MAX_WIDTH", 1200)

    @property
    def image_max_height(self) -> int:
        return self.get_int("IMAGE_MAX_HEIGHT", 800)

    @property
    def image_quality(self) -> int:
        return self.get_int("IMAGE_QUALITY", 85)

    @property
    def image_convert_webp(self) -> bool:
        return self.get_bool("IMAGE_CONVERT_WEBP", False)

    @property
    def enable_embeddings(self) -> bool:
        return self.get_bool("ENABLE_EMBEDDINGS", False)

    @property
    def embedding_model(self) -> str:
        return self.get("EMBEDDING_MODEL", "models/text-embedding-004")

    @property
    def telemetry_enabled(self) -> bool:
        return self.get_bool("TELEMETRY_ENABLED", True)

    @property
    def log_level(self) -> str:
        return self.get("LOG_LEVEL", "INFO").upper()
