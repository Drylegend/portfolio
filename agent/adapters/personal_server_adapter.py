"""
personal_server_adapter.py — SKELETON ONLY.

Future adapter for deploying to a personal/VPS server.

Planned implementation:
    - SCP or rsync files to a remote server over SSH.
    - Optionally run post-deploy scripts (e.g. nginx reload).
    - Support SSH key authentication via config.
    - Support custom remote path configuration.

Required .env additions (future):
    SERVER_HOST=your.server.com
    SERVER_USER=ubuntu
    SERVER_SSH_KEY=~/.ssh/id_rsa
    SERVER_REMOTE_PATH=/var/www/portfolio

To activate:
    1. Implement all abstract methods below.
    2. Set DEPLOYMENT_ADAPTER=personal_server in .env.
    3. Register in DeploymentService._ADAPTERS.
"""

from adapters.base_adapter import BaseDeploymentAdapter, DeploymentResult


class PersonalServerAdapter(BaseDeploymentAdapter):
    """
    SKELETON — Not yet implemented.

    Subclasses BaseDeploymentAdapter for future personal server deployment.
    """

    def __init__(self, config, logger):
        # TODO: Load SERVER_HOST, SERVER_USER, SERVER_SSH_KEY, SERVER_REMOTE_PATH
        #       from config. Validate they are present.
        raise NotImplementedError(
            "PersonalServerAdapter is not yet implemented. "
            "Set DEPLOYMENT_ADAPTER=github_pages in .env."
        )

    def prepare(self, files: list[str]) -> bool:
        # TODO: Verify SSH key exists and host is reachable.
        #       Stage files locally for rsync/scp upload.
        raise NotImplementedError

    def diff(self) -> str:
        # TODO: Run a dry-run rsync to show which files would change.
        raise NotImplementedError

    def deploy(self, message: str) -> DeploymentResult:
        # TODO: rsync/scp changed files to SERVER_REMOTE_PATH.
        #       Run any post-deploy scripts on the remote server.
        raise NotImplementedError

    def rollback(self, checkpoint: str = "") -> bool:
        # TODO: Keep a timestamped backup on the remote server.
        #       Restore from the most recent backup on rollback.
        raise NotImplementedError

    def status(self) -> str:
        # TODO: SSH to server and check web server status + last deployed file timestamps.
        raise NotImplementedError
