"""
blog/plugin.py — SKELETON ONLY.

Future plugin for automated blog post generation and publishing.

Planned responsibilities:
    - Generate a structured blog post from project description using LLM
    - Publish to a static site generator (Hugo, Jekyll, Gatsby, etc.)
    - Or POST to a CMS API (Ghost, Contentful, Hashnode, Dev.to)
    - Cross-link blog posts from the portfolio project card

Required .env additions (future):
    BLOG_PROVIDER=hashnode              # hashnode | devto | ghost | jekyll
    BLOG_API_KEY=your_api_key
    BLOG_PUBLICATION_ID=your_pub_id

Notes:
    Blog content should always be reviewed and approved before publishing.
    The LLM draft is a starting point, not a final product.
    This plugin should write to a drafts/ directory by default.
"""

from plugins.base_plugin import BasePlugin, ValidationResult


class BlogPlugin(BasePlugin):
    """
    SKELETON — Not yet implemented.

    Automated blog post generation and publishing plugin.
    """

    name    = "Blog"
    version = "0.0.0"

    def initialize(self, container) -> None:
        # TODO: Load BLOG_PROVIDER and BLOG_API_KEY from config.
        #       Verify API connectivity.
        #       Subscribe to EventBus.PROJECT_ADDED event.
        raise NotImplementedError

    def analyze(self, context: dict) -> dict:
        # TODO: Check if a blog post already exists for this project key.
        #       Return existing post URL if found.
        raise NotImplementedError

    def execute(self, payload: dict) -> dict:
        # TODO: Call LLM to draft a blog post from project description + tech_tags.
        #       Save draft to agent/memory/blog_drafts/<key>.md
        #       Show draft to user for editing before publishing.
        #       Publish on user confirmation.
        raise NotImplementedError

    def validate(self, result: dict) -> ValidationResult:
        # TODO: Verify the published post URL is accessible (HTTP 200).
        #       Check that title and project link are present in the post.
        raise NotImplementedError

    def cleanup(self, success: bool) -> None:
        # TODO: Store published post URL in projects.db blog_url column (add column).
        #       Archive the draft file.
        raise NotImplementedError
