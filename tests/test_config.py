from __future__ import annotations

from pathlib import Path

import pytest

from screenshot_inbox.config import Settings, detect_screenshot_dir, screenshot_candidates


def test_detects_first_existing_windows_candidate(tmp_path: Path) -> None:
    expected = tmp_path / "Pictures" / "Screenshots"
    expected.mkdir(parents=True)
    assert detect_screenshot_dir(user_profile=tmp_path) == expected.resolve()


def test_configured_missing_directory_is_not_accepted(tmp_path: Path) -> None:
    assert detect_screenshot_dir(str(tmp_path / "missing"), tmp_path) is None


def test_candidates_include_korean_and_onedrive_paths(tmp_path: Path) -> None:
    rendered = {str(path) for path in screenshot_candidates(tmp_path)}
    assert str(tmp_path / "Pictures" / "스크린샷") in rendered
    assert str(tmp_path / "OneDrive" / "사진" / "Screenshots") in rendered


def test_fallback_models_and_deferred_retry_delays_are_configurable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_FALLBACK_MODELS", "backup-one, backup-two,backup-one")
    monkeypatch.setenv("ANALYSIS_RETRY_DELAYS_SECONDS", "60,300,900")

    settings = Settings.from_env(tmp_path)

    assert settings.ai_fallback_models == ("backup-one", "backup-two", "backup-one")
    assert settings.analysis_retry_delays_seconds == (60.0, 300.0, 900.0)
