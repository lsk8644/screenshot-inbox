from __future__ import annotations

from pathlib import Path


def test_desktop_launcher_prefers_standalone_browser_app_mode() -> None:
    root = Path(__file__).parents[1]
    launcher = root / "launch_screenshot_inbox.ps1"
    script = launcher.read_text(encoding="utf-8")

    assert "--app=$appUrl" in script
    assert "Microsoft\\Edge\\Application\\msedge.exe" in script
    assert "Google\\Chrome\\Application\\chrome.exe" in script
    assert "Start-Process $appUrl" in script
    assert "register_notification_app.ps1" in script

    registration = (root / "register_notification_app.ps1").read_text(encoding="utf-8")
    assert "ScreenshotInbox.Local" in registration
    assert "Windows\\Start Menu\\Programs" in registration
    assert "Screenshot Inbox.lnk" in registration
    assert "ShortcutRegistration" in registration
    assert "Startup" in registration
    assert "Screenshot Inbox Background.lnk" in registration
    assert "start_screenshot_inbox_background.ps1" in registration

    background = (root / "start_screenshot_inbox_background.ps1").read_text(encoding="utf-8")
    assert "--app=" not in background
