from __future__ import annotations

import hashlib
import logging
import queue
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from screenshot_inbox.database import ScreenshotDatabase
from screenshot_inbox.providers.base import AnalyzerProvider, ProviderError
from screenshot_inbox.watcher import is_supported_image, wait_until_stable

LOGGER = logging.getLogger("screenshot_inbox")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class AnalysisPipeline:
    def __init__(
        self,
        database: ScreenshotDatabase,
        provider: AnalyzerProvider,
        *,
        max_attempts: int = 3,
        deferred_retry_delays: tuple[float, ...] = (60.0, 300.0, 900.0),
        stable_interval_seconds: float = 0.5,
        stable_checks: int = 3,
        completion_notifier: Callable[[int, str], None] | None = None,
    ) -> None:
        self.database = database
        self.provider = provider
        self.max_attempts = max_attempts
        self.deferred_retry_delays = deferred_retry_delays
        self.stable_interval_seconds = stable_interval_seconds
        self.stable_checks = stable_checks
        self.completion_notifier = completion_notifier
        self.jobs: queue.Queue[int | None] = queue.Queue()
        self.worker = threading.Thread(target=self._worker, name="analysis-worker", daemon=True)
        self._timers: list[threading.Timer] = []
        self._started = False

    def _schedule_job(self, screenshot_id: int, delay_seconds: float) -> None:
        if delay_seconds <= 0:
            self.jobs.put(screenshot_id)
            return
        timer = threading.Timer(delay_seconds, self.jobs.put, args=(screenshot_id,))
        timer.daemon = True
        self._timers.append(timer)
        timer.start()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.worker.start()
        for screenshot_id, delay_seconds in self.database.pending_jobs():
            self._schedule_job(screenshot_id, delay_seconds)

    def stop(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()
        if not self._started:
            return
        self.jobs.put(None)
        self.worker.join(timeout=10)
        self._started = False

    def ingest(self, path: Path, *, assume_stable: bool = False) -> int | None:
        if not is_supported_image(path):
            return None
        if not assume_stable and not wait_until_stable(
            path, self.stable_interval_seconds, self.stable_checks
        ):
            LOGGER.warning("[FAILED] file did not become stable: %s", path.name)
            return None
        try:
            with Image.open(path) as image:
                image.verify()
            stat = path.stat()
            digest = sha256_file(path)
        except (FileNotFoundError, PermissionError, OSError, UnidentifiedImageError) as exc:
            LOGGER.warning("[FAILED] unreadable image %s: %s", path.name, exc)
            return None
        if self.database.is_dismissed(digest):
            LOGGER.info("[NEW] dismissed screenshot ignored: %s", path.name)
            return None
        created = datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat()
        screenshot_id, inserted = self.database.insert_screenshot(path, digest, created)
        if not inserted:
            LOGGER.info("[NEW] duplicate ignored: %s", path.name)
            return screenshot_id
        LOGGER.info("[NEW] %s", path.name)
        LOGGER.info("[QUEUE] id=%s", screenshot_id)
        self.jobs.put(screenshot_id)
        return screenshot_id

    def reconcile_directory(self, directory: Path, since: datetime) -> int:
        """Queue screenshots created or changed since the previous app start."""
        before_count = self.database.count_screenshots()
        for path in sorted(directory.iterdir()):
            if not path.is_file() or not is_supported_image(path):
                continue
            try:
                stat = path.stat()
            except (FileNotFoundError, PermissionError, OSError):
                continue
            changed_at = datetime.fromtimestamp(max(stat.st_ctime, stat.st_mtime), tz=UTC)
            if changed_at >= since:
                self.ingest(path, assume_stable=True)
        recovered = self.database.count_screenshots() - before_count
        if recovered:
            LOGGER.info("[RECOVERED] queued=%s", recovered)
        return recovered

    def retry(self, screenshot_id: int) -> bool:
        if self.database.reset_for_retry(screenshot_id):
            LOGGER.info("[QUEUE] retry id=%s", screenshot_id)
            self.jobs.put(screenshot_id)
            return True
        return False

    def process_now(self, screenshot_id: int, sleep: object = time.sleep) -> None:
        record = self.database.get(screenshot_id)
        if record is None:
            return
        path = Path(record["file_path"])
        if not path.is_file():
            self.database.mark_failed(screenshot_id, "Screenshot file no longer exists", 0)
            LOGGER.error("[FAILED] id=%s file missing", screenshot_id)
            return
        attempts = 0
        retryable_failure = False
        last_error = "Analysis failed"
        while attempts < self.max_attempts:
            attempts += 1
            self.database.mark_analyzing(screenshot_id, self.provider.name, self.provider.model)
            LOGGER.info("[ANALYZING] id=%s attempt=%s", screenshot_id, attempts)
            try:
                result = self.provider.analyze(path)
                used_model = getattr(self.provider, "last_model_used", None)
                self.database.mark_completed(screenshot_id, result.as_dict(), model=used_model)
                if self.completion_notifier is not None:
                    self.completion_notifier(screenshot_id, result.title)
                LOGGER.info(
                    "[DONE] category=%s confidence=%.2f", result.category, result.confidence
                )
                return
            except ProviderError as exc:
                last_error = str(exc)
                retryable_failure = exc.retryable
                if not exc.retryable or attempts >= self.max_attempts:
                    break
                delay = min(8.0, float(2 ** (attempts - 1)))
                LOGGER.warning("[RETRY] id=%s in %.1fs: %s", screenshot_id, delay, exc)
                sleep(delay)  # type: ignore[operator]
            except Exception as exc:
                last_error = f"Unexpected analysis error: {exc}"
                retryable_failure = False
                LOGGER.exception("[FAILED] id=%s", screenshot_id)
                break
        record = self.database.get(screenshot_id)
        deferred_count = int(record.get("deferred_retry_count", 0)) if record else 0
        if retryable_failure and deferred_count < len(self.deferred_retry_delays):
            delay = self.deferred_retry_delays[deferred_count]
            self.database.defer_retry(screenshot_id, last_error, attempts, delay)
            self._schedule_job(screenshot_id, delay)
            LOGGER.warning(
                "[DEFERRED] id=%s retry=%s in %.1fs: %s",
                screenshot_id,
                deferred_count + 1,
                delay,
                last_error,
            )
            return
        self.database.mark_failed(screenshot_id, last_error, attempts)
        LOGGER.error("[FAILED] id=%s attempts=%s: %s", screenshot_id, attempts, last_error)

    def _worker(self) -> None:
        while True:
            screenshot_id = self.jobs.get()
            try:
                if screenshot_id is None:
                    return
                self.process_now(screenshot_id)
            finally:
                self.jobs.task_done()
