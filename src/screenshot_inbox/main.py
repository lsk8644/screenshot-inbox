from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from screenshot_inbox.analyzer import build_provider
from screenshot_inbox.config import Settings
from screenshot_inbox.database import ScreenshotDatabase
from screenshot_inbox.notifications import notify_analysis_complete
from screenshot_inbox.pipeline import AnalysisPipeline
from screenshot_inbox.watcher import ScreenshotWatcher
from screenshot_inbox.web import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("screenshot_inbox")
WATCH_CHECKPOINT_KEY = "watch_checkpoint_utc"


def build_application(project_root: Path | None = None) -> FastAPI:
    root = project_root or Path(__file__).resolve().parents[2]
    settings = Settings.from_env(root)
    database = ScreenshotDatabase(settings.database_path)
    database.initialize()
    pipeline = AnalysisPipeline(
        database,
        build_provider(settings),
        max_attempts=settings.max_analysis_attempts,
        deferred_retry_delays=settings.analysis_retry_delays_seconds,
        stable_interval_seconds=settings.stable_interval_seconds,
        stable_checks=settings.stable_checks,
        completion_notifier=notify_analysis_complete,
    )
    watcher: ScreenshotWatcher | None = None
    watch_directory = settings.screenshot_dir
    if watch_directory is not None:
        watcher = ScreenshotWatcher(watch_directory, pipeline.ingest)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        scan_started_at = datetime.now(UTC)
        pipeline.start()
        if watcher and watch_directory is not None:
            try:
                watcher.start()
                raw_checkpoint = database.get_state(WATCH_CHECKPOINT_KEY)
                if raw_checkpoint:
                    checkpoint = datetime.fromisoformat(raw_checkpoint)
                    if checkpoint.tzinfo is None:
                        checkpoint = checkpoint.replace(tzinfo=UTC)
                    pipeline.reconcile_directory(
                        watch_directory,
                        checkpoint.astimezone(UTC) - timedelta(seconds=2),
                    )
                database.set_state(WATCH_CHECKPOINT_KEY, scan_started_at.isoformat())
            except OSError as exc:
                LOGGER.error("[FAILED] watcher unavailable: %s", exc)
        else:
            configured = settings.screenshot_dir_configured or "automatic detection"
            LOGGER.warning("[WATCH] no screenshot directory found (%s)", configured)
        yield
        if watcher:
            watcher.stop()
        pipeline.stop()

    app = create_app(settings, database, pipeline)
    app.router.lifespan_context = lifespan
    return app


app = build_application()


def run() -> None:
    settings = Settings.from_env(Path(__file__).resolve().parents[2])
    uvicorn.run("screenshot_inbox.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
