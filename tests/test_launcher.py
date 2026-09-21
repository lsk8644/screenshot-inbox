from __future__ import annotations

from pathlib import Path


def test_desktop_launcher_prefers_standalone_browser_app_mode() -> None:
    launcher = Path(__file__).parents[1] / "launch_screenshot_inbox.ps1"
    script = launcher.read_text(encoding="utf-8")

    assert "--app=$appUrl" in script
    assert "Microsoft\\Edge\\Application\\msedge.exe" in script
    assert "Google\\Chrome\\Application\\chrome.exe" in script
    assert "Start-Process $appUrl" in script
