"""
image_processing_service.py — Image resize, compression, and format conversion.

Uses Pillow. Called by Image Agent before any new image is added to the portfolio.

Responsibilities:
    - Resize to fit within max dimensions (preserving aspect ratio)
    - Re-compress with configured quality
    - Optionally convert to WebP
    - Return image metadata (width, height, size, format, checksum)

Rules:
    - Never upscale images (only downscale if they exceed max dimensions).
    - Always overwrite the original file in assets/.
    - Compute SHA-256 BEFORE processing for dedup; record final dimensions AFTER.
"""

import hashlib
import io
from pathlib import Path


class ImageProcessingService:
    """
    Pillow-based image optimisation pipeline.
    """

    def __init__(self, config, logger):
        self._config = config
        self._logger = logger
        self._max_w  = config.image_max_width
        self._max_h  = config.image_max_height
        self._quality = config.image_quality
        self._webp   = config.image_convert_webp

    def checksum(self, path: Path) -> str:
        """Return SHA-256 hex digest of the file at *path*."""
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def process(self, path: Path) -> dict:
        """
        Resize + compress (+ optionally convert) a single image.

        Args:
            path: Absolute path to the image file.

        Returns:
            dict with keys: filepath, width, height, size_bytes, format, checksum
        """
        from PIL import Image  # imported here so startup doesn't require Pillow

        img = Image.open(path)

        # Convert RGBA/P to RGB before JPEG save
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize (never upscale)
        original_w, original_h = img.size
        if original_w > self._max_w or original_h > self._max_h:
            img.thumbnail((self._max_w, self._max_h), Image.LANCZOS)
            self._logger.info(
                f"Resized {path.name}: {original_w}×{original_h} → {img.size[0]}×{img.size[1]}"
            )

        # Determine output format
        if self._webp:
            out_path = path.with_suffix(".webp")
            save_fmt = "WEBP"
        else:
            out_path = path
            save_fmt = "JPEG"

        img.save(out_path, format=save_fmt, quality=self._quality, optimize=True)

        # Rename original if format changed
        if self._webp and out_path != path:
            path.unlink(missing_ok=True)
            path = out_path

        final_w, final_h = img.size
        size_bytes = path.stat().st_size
        checksum = self.checksum(path)

        self._logger.success(
            f"Processed {path.name}: {final_w}×{final_h}, "
            f"{size_bytes // 1024}KB, {save_fmt}"
        )

        return {
            "filepath":   str(path),
            "width":      final_w,
            "height":     final_h,
            "size_bytes": size_bytes,
            "format":     save_fmt.lower(),
            "checksum":   checksum,
        }

    def process_batch(self, paths: list[Path]) -> list[dict]:
        """Process a list of image paths and return their metadata."""
        results = []
        for p in paths:
            try:
                results.append(self.process(p))
            except Exception as exc:
                self._logger.error(f"Failed to process {p.name}: {exc}")
        return results
