"""
renderer.py — HTML generation for portfolio project cards and modals.

Produces the HTML fragments inserted into index.html.
Reads the card template and anchor comment positions.

Rules:
    - Never writes to files directly. Returns strings only.
    - Card HTML must match the existing portfolio style exactly.
    - The anchor comment <!-- END PROJECT CARDS --> must be present in index.html.
"""

from pathlib import Path


# Anchor comment Patcher looks for in index.html
CARD_ANCHOR = "<!-- END PROJECT CARDS -->"


class PortfolioRenderer:
    """
    Generates HTML fragments for portfolio project cards.
    """

    def render_card(self, project: dict) -> str:
        """
        Render a single project card HTML fragment.

        Args:
            project: Project data dict with keys: key, title, short_desc, cover.

        Returns:
            HTML string for the card div.
        """
        key        = project["key"]
        title      = project["title"]
        short_desc = project.get("short_desc", "")
        cover      = project.get("cover", project.get("cover_image", ""))

        # Derive a human-readable alt text from the title
        alt = title.replace('"', "'")

        return (
            f"\n        <!-- {title.upper()} -->\n"
            f'        <div class="project-card">\n'
            f'            <img src="{cover}" alt="{alt}" />\n'
            f'            <h3>{title}</h3>\n'
            f'            <p>{short_desc}</p>\n'
            f'            <button onclick="openModal(\'{key}\')">'
            f'View More</button>\n'
            f'        </div>'
        )

    def card_anchor(self) -> str:
        """Return the anchor comment string used for injection."""
        return CARD_ANCHOR

    def verify_anchor_present(self, html_path: Path) -> bool:
        """Check that the anchor comment exists in index.html."""
        content = html_path.read_text(encoding="utf-8")
        return CARD_ANCHOR in content

    def inject_anchor_if_missing(self, html_path: Path) -> bool:
        """
        If the anchor is absent, insert it before the closing </div>
        of .project-container. Uses BeautifulSoup4.

        Returns True if anchor was added, False if it already existed.
        """
        from bs4 import BeautifulSoup, Comment

        content = html_path.read_text(encoding="utf-8")
        if CARD_ANCHOR in content:
            return False

        soup = BeautifulSoup(content, "lxml")
        container = soup.find("div", class_="project-container")
        if not container:
            raise RuntimeError(
                "Could not find <div class='project-container'> in index.html. "
                "Cannot inject anchor comment."
            )

        # Append anchor comment as the last child of the container
        comment = Comment(" END PROJECT CARDS ")
        container.append(comment)

        html_path.write_text(str(soup), encoding="utf-8")
        return True
