from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

LOGGER = logging.getLogger("screenshot_inbox")
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def wait_until_stable(
    path: Path,
    interval_seconds: float = 0.5,
    stable_checks: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    previous: tuple[int, int] | None = None
    stable = 0
    for _ in range(max(stable_checks * 4, stable_checks + 1)):
        try:
            stat = path.stat()
            current = (stat.st_size, stat.st_mtime_ns)
            if stat.st_size > 0 and current == previous:
                stable += 1
                if stable >= stable_checks:
                    return True
            else:
                stable = 0
            previous = current
        except (FileNotFoundError, PermissionError, OSError):
            return False
        sleep(interval_seconds)
    return False


class ScreenshotEventHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[Path], object]) -> None:
        self.callback = callback

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(Path(str(event.src_path)), event.is_directory)

    def on_moved(self, event: FileSystemEvent) -> None:
        destination = getattr(event, "dest_path", event.src_path)
        self._handle(Path(str(destination)), event.is_directory)

    def _handle(self, path: Path, is_directory: bool) -> None:
        if not is_directory and is_supported_image(path):
            self.callback(path)


class ScreenshotWatcher:
    def __init__(self, directory: Path, callback: Callable[[Path], object]) -> None:
        self.directory = directory
        self.handler = ScreenshotEventHandler(callback)
        self.observer = Observer()

    def start(self) -> None:
        if not self.directory.is_dir():
            raise FileNotFoundError(f"Screenshot directory does not exist: {self.directory}")
        self.observer.schedule(self.handler, str(self.directory), recursive=False)
        self.observer.start()
        LOGGER.info("[WATCH] %s", self.directory)

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join(timeout=5)
