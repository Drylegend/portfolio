"""
container.py — Dependency Injection Container.

All components receive their dependencies via this container.
No component instantiates its own dependencies.

Boot order (dependencies first):
    1. ConfigService
    2. TimeService
    3. DatabaseService (needs config)
    4. LoggingService (needs config, time)
    5. TelemetryService (needs config, time, db)
    6. EventBus (needs logger)
    7. LLMGateway (needs config, telemetry, logger)
    8. RecoveryService (needs config, logger, time)
    9. ImageProcessingService (needs config, logger)
    10. DeploymentService (needs config, logger)
    11. Agents (need llm, db, logger, etc.)
    12. Portfolio Plugin (initialised separately after container boot)
"""

import sys
from pathlib import Path

# Ensure agent/ is on the Python path
_AGENT_DIR = Path(__file__).parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from services.config_service    import ConfigService
from services.time_service      import TimeService
from services.database_service  import DatabaseService
from services.logging_service   import LoggingService
from services.telemetry_service import TelemetryService
from services.recovery_service  import RecoveryService
from services.image_processing_service import ImageProcessingService
from services.deployment_service import DeploymentService

from core.event_bus   import EventBus
from core.llm_gateway import LLMGateway

from agents.memory_agent      import MemoryAgent
from agents.image_agent       import ImageAgent
from agents.content_agent     import ContentAgent
from agents.reflection_agent  import ReflectionAgent
from agents.validation_agent  import ValidationAgent

from plugins.portfolio.plugin import PortfolioPlugin


class Container:
    """
    Central dependency injection container.

    All components are built here in boot order.
    Agents and services must never instantiate their own dependencies.

    Extension point: add new services, agents, or plugins here.
    No other file needs to change when a new component is added.
    """

    def __init__(self):
        # ── Phase 1: Core services (no cross-dependencies) ────────────────
        self.config = ConfigService()
        self.time   = TimeService()

        # ── Phase 2: Data + Logging ────────────────────────────────────────
        # DatabaseService needs config (for memory dir path)
        # but LoggingService needs time for log filenames.
        # Bootstrap: create a minimal logger first for DB init errors.
        self.db = DatabaseService(self.config, _BootstrapLogger())
        self.logger = LoggingService(self.config, self.time)

        # Replace bootstrap logger in db with real one
        self.db._logger = self.logger

        # ── Phase 3: Telemetry + Events ───────────────────────────────────
        self.telemetry = TelemetryService(self.config, self.time, self.db)
        self.event_bus = EventBus(self.logger)

        # ── Phase 4: LLM Gateway ──────────────────────────────────────────
        self.llm = LLMGateway(self.config, self.telemetry, self.logger)

        # ── Phase 5: Infrastructure services ─────────────────────────────
        self.recovery   = RecoveryService(self.config, self.logger, self.time)
        self.img_proc   = ImageProcessingService(self.config, self.logger)
        self.deployment = DeploymentService(self.config, self.logger)

        # ── Phase 6: AI Agents ────────────────────────────────────────────
        self.memory_agent     = MemoryAgent(
            self.llm, self.db, self.logger, self.config, self.time
        )
        self.image_agent      = ImageAgent(
            self.llm, self.db, self.img_proc, self.logger, self.config
        )
        self.content_agent    = ContentAgent(
            self.llm, self.db, self.telemetry, self.logger, self.time
        )
        self.reflection_agent = ReflectionAgent(
            self.llm, self.db, self.logger, self.telemetry, self.config
        )
        self.validation_agent = ValidationAgent(
            self.db, self.logger, self.config
        )

        # ── Phase 7: Plugins ──────────────────────────────────────────────
        self.portfolio_plugin = PortfolioPlugin()
        self.portfolio_plugin.initialize(self)


class _BootstrapLogger:
    """Minimal logger used during Container boot before real LoggingService is ready."""
    def info(self, msg, **kw):    print(f"  [i] {msg}")
    def success(self, msg, **kw): print(f"  [+] {msg}")
    def warning(self, msg, **kw): print(f"  [!] {msg}")
    def error(self, msg, **kw):   print(f"  [x] {msg}")
    def agent(self, name, msg, **kw): print(f"  [{name}] {msg}")
