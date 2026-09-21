from __future__ import annotations

from pathlib import Path

from screenshot_inbox.watcher import is_supported_image, wait_until_stable


def test_supported_extensions_are_case_insensitive() -> None:
    assert is_supported_image(Path("capture.PNG"))
    assert is_supported_image(Path("capture.webp"))
    assert not is_supported_image(Path("capture.gif"))


def test_stable_file_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "capture.png"
    path.write_bytes(b"complete")
    assert wait_until_stable(path, interval_seconds=0.01, stable_checks=2, sleep=lambda _: None)


def test_missing_file_is_not_stable(tmp_path: Path) -> None:
    assert not wait_until_stable(
        tmp_path / "missing.png", interval_seconds=0.01, stable_checks=2, sleep=lambda _: None
    )
