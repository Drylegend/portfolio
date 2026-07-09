"""
image_agent.py — New image detection and project classification.

Responsibilities:
    - Scan assets/ for image files not yet in image_index.db
    - Detect SHA-256 duplicates early
    - Group new files by filename prefix
    - Classify prefix as: new project | update to existing | ambiguous
    - Call LLM Gateway ONLY when classification is ambiguous
    - Trigger ImageProcessingService for optimisation
    - Return structured classification result to Orchestrator

Rules:
    - Pure Python (prefix/suffix logic) handles the common case.
    - LLM is called only when a prefix matches no clear pattern.
    - Never makes assumptions about project assignment without confirmation.
"""

import hashlib
import re
from pathlib import Path
from dataclasses import dataclass, field


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Known role suffixes in filenames
COVER_SUFFIXES  = {"cover", "thumbnail", "thumb", "main", "hero", "banner"}
GALLERY_PATTERN = re.compile(r"_(?:img)?(\d+)$", re.IGNORECASE)


@dataclass
class ImageGroup:
    """A group of new images sharing the same project key prefix."""
    detected_key: str
    cover:        str = ""
    images:       list[str] = field(default_factory=list)
    all_files:    list[str] = field(default_factory=list)
    is_new:       bool = True      # False if key already exists in DB
    confidence:   str = "high"    # high | low (low triggers LLM check)


@dataclass
class ImageScanResult:
    """Result of the full image scan."""
    new_groups:    list[ImageGroup]
    duplicates:    list[dict]      # files with known checksums
    unclassified:  list[str]       # files that couldn't be assigned a prefix


class ImageAgent:
    """
    Detects new images in assets/ and classifies them by project.
    Uses LLM only when filename prefix is ambiguous.
    """

    def __init__(self, llm, db, img_proc, logger, config):
        self._llm      = llm
        self._db       = db
        self._img_proc = img_proc
        self._logger   = logger
        self._config   = config

    def scan(self, known_keys: set[str]) -> ImageScanResult:
        """
        Scan assets/ directory for new images.

        Args:
            known_keys: Set of project keys already in the database.

        Returns:
            ImageScanResult with classified groups, duplicates, and unclassified files.
        """
        assets_dir = self._config.assets_dir
        known_filenames = self._db.get_all_image_filenames()

        new_files: list[Path] = []
        duplicates: list[dict] = []

        # Find all untracked image files
        for f in sorted(assets_dir.iterdir()):
            if f.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if f.name in known_filenames:
                continue

            # Dedup by checksum
            checksum = self._img_proc.checksum(f)
            existing = self._db.image_exists_by_checksum(checksum)
            if existing:
                duplicates.append({
                    "filename":    f.name,
                    "duplicate_of": existing.get("filename", ""),
                    "project_key": existing.get("project_key", ""),
                })
                self._logger.warning(
                    f"Duplicate detected: {f.name} matches {existing.get('filename')}"
                )
                continue

            new_files.append(f)

        if not new_files:
            return ImageScanResult(new_groups=[], duplicates=duplicates, unclassified=[])

        self._logger.agent(
            "ImageAgent",
            f"Found {len(new_files)} new image(s) to classify."
        )

        return self._classify(new_files, known_keys, duplicates)

    def _classify(self, files: list[Path], known_keys: set[str],
                  duplicates: list[dict]) -> ImageScanResult:
        """Group files by prefix and classify each group."""
        groups: dict[str, list[Path]] = {}

        for f in files:
            prefix = self._extract_prefix(f.stem)
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append(f)

        image_groups: list[ImageGroup] = []
        unclassified: list[str] = []

        for prefix, file_list in groups.items():
            if not prefix:
                unclassified.extend([f.name for f in file_list])
                continue

            # Check if this is an ambiguous prefix
            confidence = self._assess_confidence(prefix, file_list, known_keys)

            if confidence == "low":
                # Use LLM to disambiguate
                prefix = self._llm_classify(prefix, file_list, known_keys) or prefix

            group = ImageGroup(
                detected_key=prefix,
                is_new=(prefix not in known_keys),
                confidence=confidence,
            )

            for f in file_list:
                group.all_files.append(f.name)
                stem_lower = f.stem.lower()

                # Determine cover vs gallery
                suffix_part = stem_lower.replace(prefix.lower(), "").strip("_")
                if suffix_part in COVER_SUFFIXES or not suffix_part:
                    if not group.cover:
                        group.cover = f"assets/{f.name}"
                    else:
                        group.images.append(f"assets/{f.name}")
                else:
                    group.images.append(f"assets/{f.name}")

            # If no cover found, promote first image
            if not group.cover and group.images:
                group.cover = group.images.pop(0)

            image_groups.append(group)

        return ImageScanResult(
            new_groups=image_groups,
            duplicates=duplicates,
            unclassified=unclassified,
        )

    def process_images(self, group: ImageGroup) -> list[dict]:
        """
        Run ImageProcessingService on all images in a group.

        Returns:
            List of image metadata dicts ready for image_index.db insertion.
        """
        import time

        all_paths = []
        if group.cover:
            all_paths.append(self._config.assets_dir / Path(group.cover).name)
        for img in group.images:
            all_paths.append(self._config.assets_dir / Path(img).name)

        results = []
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for path in all_paths:
            try:
                meta = self._img_proc.process(path)
                stem_lower = path.stem.lower()
                suffix = stem_lower.replace(group.detected_key.lower(), "").strip("_")
                role = "cover" if (suffix in COVER_SUFFIXES or suffix == "") else "gallery"

                results.append({
                    "filename":    path.name,
                    "filepath":    meta["filepath"],
                    "project_key": group.detected_key,
                    "role":        role,
                    "checksum":    meta["checksum"],
                    "width":       meta["width"],
                    "height":      meta["height"],
                    "size_bytes":  meta["size_bytes"],
                    "processed":   1,
                    "format":      meta["format"],
                    "added_at":    now,
                })
            except Exception as exc:
                self._logger.error(f"Failed to process {path.name}: {exc}")

        return results

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _extract_prefix(self, stem: str) -> str:
        """
        Extract the project key prefix from a filename stem.

        Examples:
            invest_cover  → invest
            weather_img1  → weather
            spark_3       → spark
            myproject     → myproject
        """
        # Remove trailing cover, imgN, N, screenshot, etc. (underscore optional)
        cleaned = re.sub(
            r"_?(cover|thumbnail|thumb|main|hero|banner|img\d+|\d+|screenshot|demo|preview)$",
            "",
            stem,
            flags=re.IGNORECASE,
        )
        return cleaned.lower()

    def _assess_confidence(self, prefix: str, files: list[Path],
                            known_keys: set[str]) -> str:
        """
        Assess whether prefix classification is confident or ambiguous.

        Returns 'high' or 'low'.
        """
        # Single-word prefixes that are common English words are ambiguous
        vague_words = {"data", "project", "image", "photo", "pic", "new",
                       "test", "demo", "sample", "screenshot"}
        if prefix in vague_words:
            return "low"

        # If no files have recognisable role suffixes, lower confidence
        has_role = any(
            re.search(
                r"_?(cover|img\d+|\d+|thumbnail|main)$", f.stem, re.IGNORECASE
            )
            for f in files
        )
        if not has_role and len(files) == 1:
            return "low"

        return "high"

    def _llm_classify(self, prefix: str, files: list[Path],
                       known_keys: set[str]) -> str | None:
        """
        Use LLM to resolve ambiguous filename prefix.

        Returns the best-guess project key, or None if truly unclassifiable.
        """
        filenames = [f.name for f in files]
        known = list(known_keys)

        prompt = (
            f"I have image files with the prefix '{prefix}': {filenames}\n"
            f"The portfolio already has these project keys: {known}\n\n"
            "Determine the most likely project key for these images. "
            "If the prefix suggests a brand-new project, return the prefix as-is. "
            "If it matches an existing key, return that key. "
            "Respond with ONLY the project key string and nothing else."
        )

        try:
            response = self._llm.generate(prompt)
            suggested = response.text.strip().lower().replace(" ", "_")
            self._logger.agent(
                "ImageAgent",
                f"LLM classified '{prefix}' → '{suggested}'"
            )
            return suggested
        except Exception as exc:
            self._logger.warning(f"LLM classification failed: {exc}")
            return None
