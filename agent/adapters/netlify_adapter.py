"""
netlify_adapter.py — SKELETON ONLY.

Future adapter for deploying to Netlify.

Planned implementation:
    - Use Netlify CLI or Netlify API to deploy site files.
    - Support deploy previews (branch deploys).
    - Retrieve deploy URL from API response.
    - Support rollback via Netlify deploy lock/unlock.

Required .env additions (future):
    NETLIFY_AUTH_TOKEN=your_netlify_token
    NETLIFY_SITE_ID=your_site_id

To activate:
    1. Implement all abstract methods below.
    2. Set DEPLOYMENT_ADAPTER=netlify in .env.
    3. Register in DeploymentService._ADAPTERS.

Reference: https://docs.netlify.com/api/get-started/
"""

from adapters.base_adapter import BaseDeploymentAdapter, DeploymentResult


class NetlifyAdapter(BaseDeploymentAdapter):
    """
    SKELETON — Not yet implemented.

    Subclasses BaseDeploymentAdapter for future Netlify deployment.
    """

    def __init__(self, config, logger):
        # TODO: Load NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID from config.
        #       Validate tokens are present and not placeholder values.
        raise NotImplementedError(
            "NetlifyAdapter is not yet implemented. "
            "Set DEPLOYMENT_ADAPTER=github_pages in .env."
        )

    def prepare(self, files: list[str]) -> bool:
        # TODO: Validate all files exist locally.
        #       Optionally run netlify build if a build step is configured.
        raise NotImplementedError

    def diff(self) -> str:
        # TODO: Compare local files with Netlify CDN to show what would change.
        #       Could use file checksums against the Netlify Files API.
        raise NotImplementedError

    def deploy(self, message: str) -> DeploymentResult:
        # TODO: POST to Netlify Deploy API with the site directory.
        #       Poll deploy status until success or timeout.
        #       Return deploy URL from API response.
        raise NotImplementedError

    def rollback(self, checkpoint: str = "") -> bool:
        # TODO: Use Netlify API to restore a previous deploy by deploy_id.
        #       Netlify keeps full deploy history per site.
        raise NotImplementedError

    def status(self) -> str:
        # TODO: GET /sites/{site_id}/deploys to show last deploy status and URL.
        raise NotImplementedError
