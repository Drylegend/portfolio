"""
linkedin/plugin.py — SKELETON ONLY.

Future plugin for automated LinkedIn profile updates.

Planned responsibilities:
    - Use LinkedIn API to post project announcements
    - Update "Featured" section with new project links
    - Add new skills extracted from project tech_tags
    - Create posts or articles summarising new projects

Required .env additions (future):
    LINKEDIN_ACCESS_TOKEN=your_oauth_token
    LINKEDIN_PROFILE_ID=your_profile_urn

Notes:
    LinkedIn API requires OAuth 2.0 and has strict rate limits.
    Posts should be queued and approved before publishing.
    This plugin should ALWAYS show a preview and require confirmation.

Reference: https://learn.microsoft.com/en-us/linkedin/marketing/
"""

from plugins.base_plugin import BasePlugin, ValidationResult


class LinkedInPlugin(BasePlugin):
    """
    SKELETON — Not yet implemented.

    Automated LinkedIn post and profile update plugin.
    """

    name    = "LinkedIn"
    version = "0.0.0"

    def initialize(self, container) -> None:
        # TODO: Load LINKEDIN_ACCESS_TOKEN from config.
        #       Verify token is valid via GET /userinfo.
        #       Subscribe to EventBus.PROJECT_ADDED event.
        raise NotImplementedError

    def analyze(self, context: dict) -> dict:
        # TODO: Fetch recent LinkedIn posts to avoid duplicate announcements.
        #       Return list of recently posted project keys.
        raise NotImplementedError

    def execute(self, payload: dict) -> dict:
        # TODO: Draft a LinkedIn post from project title, description, and GitHub link.
        #       Show draft to user for confirmation before publishing.
        #       POST to LinkedIn Share API if user confirms.
        raise NotImplementedError

    def validate(self, result: dict) -> ValidationResult:
        # TODO: Verify API returned 201 Created with a post URN.
        #       Confirm the post is visible at the returned URL.
        raise NotImplementedError

    def cleanup(self, success: bool) -> None:
        # TODO: Store published post URN in project history for reference.
        raise NotImplementedError
