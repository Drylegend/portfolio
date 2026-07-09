"""
documentation/plugin.py — SKELETON ONLY.

Future plugin for automated project documentation generation.

Planned responsibilities:
    - Generate README.md for each project from description and metadata
    - Generate API documentation if a GitHub repo is provided (via repo scan)
    - Publish documentation to GitHub Wiki or a docs site (MkDocs, Sphinx)
    - Keep documentation in sync with portfolio metadata changes

Required .env additions (future):
    DOCS_PROVIDER=github_wiki          # github_wiki | mkdocs | sphinx | readme_io
    DOCS_OUTPUT_DIR=docs/

Notes:
    Documentation generation is a write operation on external repos.
    Always requires explicit user confirmation before committing.
    Generated docs should be saved locally first for review.
"""

from plugins.base_plugin import BasePlugin, ValidationResult


class DocumentationPlugin(BasePlugin):
    """
    SKELETON — Not yet implemented.

    Automated project documentation generation plugin.
    """

    name    = "Documentation"
    version = "0.0.0"

    def initialize(self, container) -> None:
        # TODO: Load DOCS_PROVIDER and output paths from config.
        #       Verify LLM Gateway is available (used for README generation).
        #       Subscribe to EventBus.PROJECT_ADDED event.
        raise NotImplementedError

    def analyze(self, context: dict) -> dict:
        # TODO: For each project in the portfolio, check if a README exists.
        #       Return list of projects missing documentation.
        raise NotImplementedError

    def execute(self, payload: dict) -> dict:
        # TODO: Call LLM to generate a structured README.md from:
        #           - project title, description, tech_tags, github_url
        #           - optionally scan the GitHub repo for file structure
        #       Save README.md to a docs_drafts/ directory.
        #       Show to user for review before committing.
        raise NotImplementedError

    def validate(self, result: dict) -> ValidationResult:
        # TODO: Validate that the generated README is non-empty.
        #       Verify it contains required sections (Overview, Tech Stack, Usage).
        raise NotImplementedError

    def cleanup(self, success: bool) -> None:
        # TODO: Store docs URL in projects.db (add docs_url column).
        #       Archive draft file.
        raise NotImplementedError
