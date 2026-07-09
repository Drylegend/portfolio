"""
deployment_service.py — Loads the correct adapter and coordinates deployment.

This service is the boundary between the Workflow Manager and the
adapter layer. It never hardcodes a deployment target.

Rules:
    - Adapter is selected from DEPLOYMENT_ADAPTER in .env.
    - Adding a new adapter requires only registering it in _ADAPTERS.
    - This service never calls git, rsync, or any provider API directly.
"""

from adapters.base_adapter import BaseDeploymentAdapter, DeploymentResult


class DeploymentService:
    """
    Loads and delegates to the configured deployment adapter.

    Extension point: register new adapters in _ADAPTERS dict.
    No other file needs to change when a new adapter is added.
    """

    # Registry: adapter name (from .env) → module path + class name
    # To add a new adapter: insert one entry here.
    _ADAPTERS = {
        "github_pages":    ("adapters.github_pages_adapter",    "GitHubPagesAdapter"),
        "personal_server": ("adapters.personal_server_adapter", "PersonalServerAdapter"),
        "netlify":         ("adapters.netlify_adapter",         "NetlifyAdapter"),
    }

    def __init__(self, config, logger):
        self._config = config
        self._logger = logger
        self._adapter: BaseDeploymentAdapter = self._load_adapter()

    def prepare(self, files: list[str]) -> bool:
        return self._adapter.prepare(files)

    def diff(self) -> str:
        return self._adapter.diff()

    def deploy(self, message: str) -> DeploymentResult:
        return self._adapter.deploy(message)

    def rollback(self, checkpoint: str = "") -> bool:
        return self._adapter.rollback(checkpoint)

    def status(self) -> str:
        return self._adapter.status()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _load_adapter(self) -> BaseDeploymentAdapter:
        adapter_name = self._config.deployment_adapter
        if adapter_name not in self._ADAPTERS:
            available = ", ".join(self._ADAPTERS.keys())
            raise ValueError(
                f"Unknown DEPLOYMENT_ADAPTER: '{adapter_name}'. "
                f"Available: {available}"
            )

        module_path, class_name = self._ADAPTERS[adapter_name]

        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        self._logger.info(f"Deployment adapter: {class_name}")
        return cls(self._config, self._logger)
