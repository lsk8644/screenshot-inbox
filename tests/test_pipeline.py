from __future__ import annotations

from pathlib import Path

from screenshot_inbox.database import ScreenshotDatabase
from screenshot_inbox.pipeline import AnalysisPipeline, sha256_file
from screenshot_inbox.providers.base import ProviderError
from screenshot_inbox.schemas import AnalysisResult


class SuccessProvider:
    name = "success"
    model = "fixture"

    def analyze(self, image_path: Path) -> AnalysisResult:
        return AnalysisResult("problem", 0.9, "Test problem", "Summary", "", {})


class FailingProvider:
    name = "failing"
    model = "fixture"

    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, image_path: Path) -> AnalysisResult:
        self.calls += 1
        raise ProviderError("503 unavailable", retryable=True, status_code=503)


def test_hash_is_content_based(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.write_bytes(b"identical")
    second.write_bytes(b"identical")
    assert sha256_file(first) == sha256_file(second)


def test_ingest_prevents_duplicate_analysis(tmp_path: Path, image_path: Path) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    pipeline = AnalysisPipeline(
        database, SuccessProvider(), stable_interval_seconds=0.01, stable_checks=1
    )
    first_id = pipeline.ingest(image_path)
    second_id = pipeline.ingest(image_path)
    assert first_id == second_id
    assert len(database.list_screenshots()) == 1


def test_successful_processing_updates_database(tmp_path: Path, image_path: Path) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(image_path, sha256_file(image_path), "2026-01-01")
    pipeline = AnalysisPipeline(database, SuccessProvider())
    pipeline.process_now(screenshot_id)
    record = database.get(screenshot_id)
    assert record is not None
    assert record["status"] == "completed"
    assert record["category"] == "problem"


def test_retry_limit_marks_failed(tmp_path: Path, image_path: Path) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(image_path, sha256_file(image_path), "2026-01-01")
    provider = FailingProvider()
    pipeline = AnalysisPipeline(database, provider, max_attempts=3)
    pipeline.process_now(screenshot_id, sleep=lambda _: None)
    record = database.get(screenshot_id)
    assert record is not None
    assert provider.calls == 3
    assert record["status"] == "failed"
    assert record["retry_count"] == 3
