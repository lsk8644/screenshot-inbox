from __future__ import annotations

import base64
import subprocess
from typing import Any

from screenshot_inbox.notifications import notify_analysis_complete


def test_windows_notification_uses_safe_environment(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_popen(command: list[str], **options: Any) -> object:
        captured["command"] = command
        captured["options"] = options
        return object()

    monkeypatch.setattr("screenshot_inbox.notifications.sys.platform", "win32")
    monkeypatch.setattr("screenshot_inbox.notifications.subprocess.Popen", fake_popen)

    notify_analysis_complete(12, "  Fork-Join\n분석  ")

    command = captured["command"]
    options = captured["options"]
    assert command[0].endswith("powershell.exe")
    assert "-EncodedCommand" in command
    script = base64.b64decode(command[-1]).decode("utf-16-le")
    assert "Get-StartApps" in script
    assert "CreateToastNotifier($appId)" in script
    assert "Microsoft.Windows.PowerShell" not in script
    assert options["env"]["SCREENSHOT_INBOX_TOAST_BODY"] == "Fork-Join 분석"
    assert options["env"]["SCREENSHOT_INBOX_TOAST_URL"].endswith("/screenshots/12")
    assert options["stdout"] is subprocess.DEVNULL
    assert options["stderr"] is subprocess.DEVNULL
