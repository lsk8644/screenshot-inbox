from __future__ import annotations

from pathlib import Path

from screenshot_inbox.config import detect_screenshot_dir, screenshot_candidates


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
