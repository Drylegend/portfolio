"""
reflection_agent.py — Quality and consistency review of Content Agent output.

Sits between ContentAgent and ValidationAgent in the pipeline.

Responsibilities:
    - Review extracted metadata for clarity, consistency, and style
    - Detect duplication with existing portfolio projects
    - Check formatting and readability
    - Either ACCEPT or REJECT with structured feedback
    - Rejection triggers Content Agent revision (max MAX_REVISION_ATTEMPTS)

Rules:
    - This agent calls the LLM once per review.
    - It does NOT re-extract metadata — it reviews the existing extraction.
    - Rejection feedback must be specific enough for Content Agent to act on.
    - After MAX_REVISION_ATTEMPTS rejections, escalate to user for manual resolution.
"""

import json
from dataclasses import dataclass, field


@dataclass
class ReflectionResult:
    """Result returned by ReflectionAgent.review()."""
    accepted:  bool
    score:     int              # 0-100
    feedback:  list[str]        = field(default_factory=list)   # issues found
    warnings:  list[str]        = field(default_factory=list)   # non-blocking notes
    revision_prompt: str        = ""    # sent to ContentAgent on rejection


REFLECTION_SYSTEM = """You are a senior portfolio reviewer for a software engineer's project portfolio.

Your task is to review extracted project metadata and assess its quality.

Evaluate for:
1. CONSISTENCY — Does the title match the description? Are tech tags consistent with the described work?
2. CLARITY — Is short_desc suitable for a non-technical audience? Is full_desc technically accurate?
3. DUPLICATION — Does this project sound too similar to the existing portfolio entries?
4. FORMATTING — Is the text free of markdown, HTML tags, quotes, or special characters?
5. READABILITY — Does short_desc fit in 1-2 sentences? Does full_desc fit in 2-4 sentences?
6. COMPLETENESS — Are tech_tags, category, and keywords populated meaningfully?
7. STYLE — Does the tone match a professional portfolio? No emojis, no first person in descs.

Respond ONLY with valid JSON in this exact structure:
{
  "accepted": true or false,
  "score": 0-100,
  "issues": ["list of specific problems if not accepted"],
  "warnings": ["list of non-blocking style notes"],
  "revision_instruction": "precise instruction for the Content Agent if rejected, empty string if accepted"
}"""


class ReflectionAgent:
    """
    Reviews Content Agent output before it reaches the Validation Agent.

    If rejected: sends revision_instruction back through the Orchestrator.
    If accepted: passes to ValidationAgent unchanged.
    """

    def __init__(self, llm, db, logger, telemetry, config):
        self._llm       = llm
        self._db        = db
        self._logger    = logger
        self._telemetry = telemetry
        self._max_attempts = config.max_revision_attempts

    def review(
        self,
        metadata,               # ProjectMetadata from ContentAgent
        existing_projects: list[dict],
    ) -> ReflectionResult:
        """
        Review extracted metadata for quality and consistency.

        Args:
            metadata:          ProjectMetadata returned by ContentAgent.
            existing_projects: List of existing project dicts from the DB.

        Returns:
            ReflectionResult with accepted/rejected decision and feedback.
        """
        self._logger.agent("ReflectionAgent", f"Reviewing: '{metadata.title}'")

        # Build existing project summary for duplication check
        existing_summary = "\n".join(
            f"- {p['key']}: {p.get('title', '')} | {p.get('short_desc', '')}"
            for p in existing_projects
        )

        prompt = (
            f"EXISTING PORTFOLIO PROJECTS:\n{existing_summary or 'None'}\n\n"
            f"METADATA TO REVIEW:\n"
            f"key:            {metadata.key}\n"
            f"title:          {metadata.title}\n"
            f"short_desc:     {metadata.short_desc}\n"
            f"full_desc:      {metadata.full_desc}\n"
            f"category:       {metadata.category}\n"
            f"difficulty:     {metadata.difficulty}\n"
            f"tech_tags:      {', '.join(metadata.tech_tags)}\n"
            f"keywords:       {', '.join(metadata.keywords)}\n"
            f"github_url:     {metadata.github_url}\n"
            f"project_purpose:{metadata.project_purpose}"
        )

        response = self._llm.generate(
            prompt=prompt,
            system=REFLECTION_SYSTEM,
            schema={},
        )

        result = self._parse_response(response.text)

        if result.accepted:
            self._logger.agent(
                "ReflectionAgent",
                f"Accepted (score: {result.score}/100)"
            )
        else:
            self._telemetry.record_reflection_rejection()
            self._logger.agent(
                "ReflectionAgent",
                f"Rejected (score: {result.score}/100). Issues: {result.feedback}"
            )

        return result

    # ── Internal ─────────────────────────────────────────────────────────────

    def _parse_response(self, text: str) -> ReflectionResult:
        """Parse LLM reflection response into ReflectionResult."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # If parsing fails, default to accepted with a warning
            self._logger.warning("ReflectionAgent: Could not parse LLM response. Defaulting to accept.")
            return ReflectionResult(accepted=True, score=70,
                                    warnings=["Reflection response could not be parsed."])

        return ReflectionResult(
            accepted=bool(data.get("accepted", True)),
            score=int(data.get("score", 70)),
            feedback=data.get("issues", []),
            warnings=data.get("warnings", []),
            revision_prompt=data.get("revision_instruction", ""),
        )
