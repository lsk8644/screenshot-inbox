from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from screenshot_inbox.schemas import AnalysisResult


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, *, retryable: bool = False, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class AnalyzerProvider(Protocol):
    name: str
    model: str | None

    def analyze(self, image_path: Path) -> AnalysisResult: ...

    def chat(
        self, image_path: Path, history: list[dict[str, Any]], question: str
    ) -> str: ...
