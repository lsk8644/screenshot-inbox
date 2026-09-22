from __future__ import annotations

from pathlib import Path
from typing import Any

from screenshot_inbox.config import Settings
from screenshot_inbox.providers.base import AnalyzerProvider, ProviderError
from screenshot_inbox.providers.mock import MockProvider
from screenshot_inbox.providers.openai_compatible import OpenAICompatibleProvider
from screenshot_inbox.schemas import AnalysisResult


class UnavailableProvider:
    name = "unavailable"
    model: str | None = None

    def __init__(self, message: str) -> None:
        self.message = message

    def analyze(self, image_path: Path) -> AnalysisResult:
        raise ProviderError(self.message)

    def chat(self, image_path: Path, history: list[dict[str, Any]], question: str) -> str:
        raise ProviderError(self.message)


def build_provider(settings: Settings) -> AnalyzerProvider:
    if settings.ai_provider == "mock":
        return MockProvider()
    if settings.ai_provider in {"openai", "openai-compatible"}:
        if not settings.ai_api_key:
            return UnavailableProvider("AI_API_KEY is not configured")
        if not settings.ai_model:
            return UnavailableProvider("AI_MODEL is not configured")
        return OpenAICompatibleProvider(
            settings.ai_base_url,
            settings.ai_api_key,
            settings.ai_model,
            settings.ai_timeout_seconds,
            fallback_models=settings.ai_fallback_models,
        )
    return UnavailableProvider(f"Unknown AI_PROVIDER: {settings.ai_provider}")
