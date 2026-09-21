from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys

LOGGER = logging.getLogger("screenshot_inbox")

_TOAST_SCRIPT = "\n".join(
    (
        "$ErrorActionPreference = 'Stop'",
        (
            "[Windows.UI.Notifications.ToastNotificationManager, "
            "Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null"
        ),
        (
            "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
            "ContentType = WindowsRuntime] | Out-Null"
        ),
        "$title = [Security.SecurityElement]::Escape($env:SCREENSHOT_INBOX_TOAST_TITLE)",
        "$body = [Security.SecurityElement]::Escape($env:SCREENSHOT_INBOX_TOAST_BODY)",
        "$url = [Security.SecurityElement]::Escape($env:SCREENSHOT_INBOX_TOAST_URL)",
        (
            "$xml = \"<toast activationType='protocol' launch='$url'><visual><binding "
            "template='ToastGeneric'><text>$title</text><text>$body</text></binding>"
            "</visual></toast>\""
        ),
        "$document = New-Object Windows.Data.Xml.Dom.XmlDocument",
        "$document.LoadXml($xml)",
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($document)",
        "$appId = 'ScreenshotInbox.Local'",
        (
            r"$registryPath = 'HKCU:\Software\Classes\AppUserModelId\' + $appId"
        ),
        "New-Item -Path $registryPath -Force | Out-Null",
        (
            "New-ItemProperty -Path $registryPath -Name 'DisplayName' "
            "-Value 'Screenshot Inbox' -PropertyType String -Force | Out-Null"
        ),
        (
            "New-ItemProperty -Path $registryPath -Name 'ShowInSettings' "
            "-Value 1 -PropertyType DWord -Force | Out-Null"
        ),
        (
            "[Windows.UI.Notifications.ToastNotificationManager]::"
            "CreateToastNotifier($appId).Show($toast)"
        ),
    )
)


def notify_analysis_complete(screenshot_id: int, title: str) -> None:
    """Show a native Windows toast without requiring an open browser."""
    if sys.platform != "win32":
        return
    encoded_script = base64.b64encode(_TOAST_SCRIPT.encode("utf-16-le")).decode("ascii")
    environment = os.environ.copy()
    environment.update(
        {
            "SCREENSHOT_INBOX_TOAST_TITLE": "Screenshot Inbox · 분석 완료",
            "SCREENSHOT_INBOX_TOAST_BODY": " ".join(title.split())[:240],
            "SCREENSHOT_INBOX_TOAST_URL": (
                f"http://127.0.0.1:8765/screenshots/{int(screenshot_id)}"
            ),
        }
    )
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(  # noqa: S603
            [
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                encoded_script,
            ],
            env=environment,
            creationflags=creation_flags,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        LOGGER.warning("[NOTIFY] Windows notification unavailable: %s", exc)
