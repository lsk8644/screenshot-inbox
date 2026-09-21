from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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


def build_application(project_root: Path | None = None) -> FastAPI:
    root = project_root or Path(__file__).resolve().parents[2]
    settings = Settings.from_env(root)
    database = ScreenshotDatabase(settings.database_path)
    database.initialize()
    pipeline = AnalysisPipeline(
        database,
        build_provider(settings),
        max_attempts=settings.max_analysis_attempts,
        stable_interval_seconds=settings.stable_interval_seconds,
        stable_checks=settings.stable_checks,
        completion_notifier=notify_analysis_complete,
    )
    watcher: ScreenshotWatcher | None = None
    if settings.screenshot_dir is not None:
        watcher = ScreenshotWatcher(settings.screenshot_dir, pipeline.ingest)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        pipeline.start()
        if watcher:
            try:
                watcher.start()
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
