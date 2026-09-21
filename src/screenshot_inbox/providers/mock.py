from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from screenshot_inbox.schemas import DETAIL_DEFAULTS, AnalysisResult, Category


class MockProvider:
    name = "mock"
    model: str | None = "local-deterministic"

    def analyze(self, image_path: Path) -> AnalysisResult:
        with Image.open(image_path) as image:
            width, height = image.size
        stem = image_path.stem.lower()
        category: Category = "other"
        for candidate in ("error", "problem", "lecture", "notice", "code", "document"):
            if candidate in stem:
                category = candidate
                break
        return AnalysisResult(
            category=category,
            confidence=0.25 if category == "other" else 0.7,
            title=image_path.stem.replace("_", " ").replace("-", " ").strip().title(),
            summary=(
                f"Mock analysis for a {width}×{height} image. "
                "Configure an AI provider for content analysis."
            ),
            extracted_text="",
            details={
                key: value.copy() if isinstance(value, list) else value
                for key, value in DETAIL_DEFAULTS[category].items()
            },
        )

    def chat(self, image_path: Path, history: list[dict[str, Any]], question: str) -> str:
        return f"Mock 답변: {question}"
