"""
content_agent.py — Extracts structured project metadata from natural language descriptions.

Responsibilities:
    - Accept a free-form project description from the user
    - Call LLM Gateway with a structured extraction prompt
    - Return a typed ProjectMetadata object
    - All token usage is forwarded to TelemetryService via the gateway

Rules:
    - The agent NEVER infers file paths or image lists from the description.
      Those come from ImageAgent and are passed in as context.
    - The agent must ALWAYS populate the semantic fields (category, keywords, etc.)
      in addition to the presentation fields (title, short_desc, full_desc).
    - Structured JSON output is requested via the schema parameter.
"""

import json
from dataclasses import dataclass, field


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title":           {"type": "string"},
        "short_desc":      {"type": "string", "description": "1-2 sentences max"},
        "full_desc":       {"type": "string", "description": "2-4 sentences"},
        "github_url":      {"type": "string"},
        "tech_tags":       {"type": "array",  "items": {"type": "string"}},
        "frameworks":      {"type": "array",  "items": {"type": "string"}},
        "languages":       {"type": "array",  "items": {"type": "string"}},
        "algorithms":      {"type": "array",  "items": {"type": "string"}},
        "datasets":        {"type": "array",  "items": {"type": "string"}},
        "category":        {"type": "string", "enum": ["ML", "Web", "Data", "Tool", "Research", "Other"]},
        "business_domain": {"type": "string"},
        "difficulty":      {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced"]},
        "project_purpose": {"type": "string", "description": "One-line purpose statement"},
        "keywords":        {"type": "array",  "items": {"type": "string"}},
        "year":            {"type": "integer"},
    },
    "required": ["title", "short_desc", "full_desc", "category", "difficulty", "tech_tags"],
}

SYSTEM_PROMPT = """You are a technical writer specialising in developer portfolio metadata extraction.

Your task is to extract structured project information from a developer's natural language description.

Rules:
- short_desc: 1-2 sentences, plain English, suitable for a project card preview.
- full_desc: 2-4 sentences, technical but readable, suitable for a project modal popup.
- tech_tags: extract specific technologies, tools, libraries, and APIs mentioned.
- frameworks: only framework names (React, FastAPI, Spark, etc.), not general tools.
- languages: programming languages only (Python, JavaScript, Java, etc.).
- algorithms: ML algorithms, statistical methods, or computational approaches mentioned.
- datasets: specific datasets or data sources mentioned.
- category: classify the project as one of: ML, Web, Data, Tool, Research, Other.
- difficulty: assess based on technologies and complexity described.
- keywords: 5-10 searchable terms that capture the project's core concepts.
- year: extract if mentioned, otherwise return the current year.
- github_url: extract if present in the description, otherwise return empty string.
- business_domain: the industry/domain this project applies to (Finance, Healthcare, Climate, etc.).

Always respond with valid JSON matching the schema. No additional text."""


@dataclass
class ProjectMetadata:
    """Structured project metadata extracted by ContentAgent."""
    key:              str
    title:            str
    short_desc:       str
    full_desc:        str
    github_url:       str               = ""
    cover_image:      str               = ""
    images:           list[str]         = field(default_factory=list)
    tech_tags:        list[str]         = field(default_factory=list)
    frameworks:       list[str]         = field(default_factory=list)
    languages:        list[str]         = field(default_factory=list)
    algorithms:       list[str]         = field(default_factory=list)
    datasets:         list[str]         = field(default_factory=list)
    category:         str               = "Other"
    business_domain:  str               = ""
    difficulty:       str               = "Intermediate"
    project_purpose:  str               = ""
    keywords:         list[str]         = field(default_factory=list)
    related_projects: list[str]         = field(default_factory=list)
    year:             int               = 0
    _image_records:   list[dict]        = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to plain dict for patching and DB insertion."""
        import dataclasses
        return dataclasses.asdict(self)


class ContentAgent:
    """
    Extracts structured project metadata from a natural language description.
    Calls LLM Gateway once per invocation.
    """

    def __init__(self, llm, db, telemetry, logger, time_service):
        self._llm       = llm
        self._db        = db
        self._telemetry = telemetry
        self._logger    = logger
        self._time      = time_service

    def extract(
        self,
        description: str,
        project_key: str,
        image_group,          # ImageGroup from ImageAgent
    ) -> ProjectMetadata:
        """
        Extract structured metadata from a raw project description.

        Args:
            description:  Free-form text from the user.
            project_key:  Pre-assigned key from ImageAgent.
            image_group:  ImageGroup containing cover and image lists.

        Returns:
            ProjectMetadata with all fields populated.
        """
        self._logger.agent("ContentAgent", "Extracting project metadata from description…")

        # Build context for the LLM
        context = (
            f"Project key: {project_key}\n"
            f"Cover image: {image_group.cover}\n"
            f"Gallery images: {', '.join(image_group.images) if image_group.images else 'none'}\n\n"
            f"Developer description:\n{description}"
        )

        response = self._llm.generate(
            prompt=context,
            system=SYSTEM_PROMPT,
            schema=EXTRACTION_SCHEMA,
        )

        # Parse JSON response
        try:
            data = self._parse_json(response.text)
        except ValueError as exc:
            self._logger.error(f"ContentAgent: Failed to parse LLM response: {exc}")
            raise

        # Populate and return ProjectMetadata
        metadata = ProjectMetadata(
            key=project_key,
            title=data.get("title", project_key.replace("_", " ").title()),
            short_desc=data.get("short_desc", ""),
            full_desc=data.get("full_desc", ""),
            github_url=data.get("github_url", ""),
            cover_image=image_group.cover,
            images=[image_group.cover] + image_group.images if image_group.cover else image_group.images,
            tech_tags=data.get("tech_tags", []),
            frameworks=data.get("frameworks", []),
            languages=data.get("languages", []),
            algorithms=data.get("algorithms", []),
            datasets=data.get("datasets", []),
            category=data.get("category", "Other"),
            business_domain=data.get("business_domain", ""),
            difficulty=data.get("difficulty", "Intermediate"),
            project_purpose=data.get("project_purpose", ""),
            keywords=data.get("keywords", []),
            year=data.get("year", self._time.year()),
        )

        self._logger.agent(
            "ContentAgent",
            f"Extracted: '{metadata.title}' | {metadata.category} | {metadata.difficulty}"
        )
        return metadata

    # ── Internal ─────────────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> dict:
        """
        Parse JSON from LLM response text.
        Handles common cases where the model wraps JSON in markdown code fences.
        """
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            inner = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )
            cleaned = inner.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM returned invalid JSON: {exc}\nResponse was:\n{text[:500]}"
            ) from exc
