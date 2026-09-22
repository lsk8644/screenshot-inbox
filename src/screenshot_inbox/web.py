from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from screenshot_inbox.config import Settings
from screenshot_inbox.database import ScreenshotDatabase
from screenshot_inbox.pipeline import AnalysisPipeline
from screenshot_inbox.providers.base import ProviderError
from screenshot_inbox.schemas import CATEGORIES

SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")


def _inline_markdown(value: str) -> str:
    text = str(escape(value))
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render_markdown(value: str) -> Markup:
    output: list[str] = []
    code_lines: list[str] = []
    in_code = False
    list_kind: str | None = None
    code_language = ""

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            output.append(f"</{list_kind}>")
            list_kind = None

    for raw_line in value.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_code:
                language = re.sub(r"[^a-zA-Z0-9_+-]", "", code_language)
                class_name = f' class="language-{language}"' if language else ""
                code = "\n".join(str(escape(item)) for item in code_lines)
                output.append(f"<pre><code{class_name}>{code}</code></pre>")
                code_lines = []
                code_language = ""
                in_code = False
            else:
                close_list()
                code_language = line[3:].strip()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        unordered = re.match(r"^\s*[-*]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if unordered or ordered:
            kind = "ul" if unordered else "ol"
            if list_kind != kind:
                close_list()
                output.append(f"<{kind}>")
                list_kind = kind
            match = unordered or ordered
            if match:
                output.append(f"<li>{_inline_markdown(match.group(1))}</li>")
            continue
        close_list()
        if not line.strip():
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            level = min(4, len(heading.group(1)) + 2)
            output.append(f"<h{level}>{_inline_markdown(heading.group(2))}</h{level}>")
        elif line.startswith("> "):
            output.append(f"<blockquote>{_inline_markdown(line[2:])}</blockquote>")
        else:
            output.append(f"<p>{_inline_markdown(line)}</p>")

    close_list()
    if in_code:
        language = re.sub(r"[^a-zA-Z0-9_+-]", "", code_language)
        class_name = f' class="language-{language}"' if language else ""
        code = "\n".join(str(escape(item)) for item in code_lines)
        output.append(f"<pre><code{class_name}>{code}</code></pre>")
    return Markup("\n".join(output))


def _with_seoul_timestamps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        raw = item.get("created_at") or item.get("detected_at")
        if not raw:
            item.update(date_key="", date_label="날짜 없음", time_label="--:--")
            continue
        detected = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if detected.tzinfo is None:
            detected = detected.replace(tzinfo=UTC)
        local = detected.astimezone(SEOUL)
        item.update(
            detected_at_iso=local.isoformat(),
            date_key=local.strftime("%Y-%m-%d"),
            date_label=f"{local.month}.{local.day:02d}",
            time_label=local.strftime("%H:%M"),
        )
    return items


def create_app(
    settings: Settings, database: ScreenshotDatabase, pipeline: AnalysisPipeline
) -> FastAPI:
    app = FastAPI(title="Screenshot Inbox", docs_url="/api/docs", redoc_url=None)
    templates = Jinja2Templates(directory=settings.project_root / "templates")
    templates.env.filters["markdown"] = render_markdown
    app.mount("/static", StaticFiles(directory=settings.project_root / "static"), name="static")
    app.state.settings = settings
    app.state.database = database
    app.state.pipeline = pipeline

    def context(request: Request, **values: Any) -> dict[str, Any]:
        return {
            "request": request,
            "categories": CATEGORIES,
            "watch_directory": settings.screenshot_dir,
            "provider": pipeline.provider.name,
            **values,
        }

    @app.get("/", response_class=HTMLResponse)
    def inbox(request: Request, category: str | None = None) -> HTMLResponse:
        selected = category if category in CATEGORIES else None
        items = _with_seoul_timestamps(database.list_screenshots(selected))
        return templates.TemplateResponse(
            request,
            "index.html",
            context(
                request,
                items=items,
                selected_category=selected,
            ),
        )

    @app.get("/screenshots/{screenshot_id}", response_class=HTMLResponse)
    def detail(request: Request, screenshot_id: int) -> HTMLResponse:
        item = database.get(screenshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Screenshot not found")
        return templates.TemplateResponse(
            request,
            "detail.html",
            context(
                request,
                item=item,
                messages=database.list_chat_messages(screenshot_id),
                chat_error=request.query_params.get("chat_error"),
            ),
        )

    @app.get("/screenshots/{screenshot_id}/image")
    def image(screenshot_id: int) -> FileResponse:
        item = database.get(screenshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Screenshot not found")
        path = Path(item["file_path"])
        if not path.is_file():
            raise HTTPException(
                status_code=410, detail="Original screenshot is no longer available"
            )
        return FileResponse(path)

    @app.post("/screenshots/{screenshot_id}/retry")
    def retry(screenshot_id: int) -> RedirectResponse:
        item = database.get(screenshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Screenshot not found")
        pipeline.retry(screenshot_id)
        return RedirectResponse(f"/screenshots/{screenshot_id}", status_code=303)

    @app.post("/screenshots/{screenshot_id}/chat")
    def chat(screenshot_id: int, question: str = Form(...)) -> RedirectResponse:
        item = database.get(screenshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Screenshot not found")
        text = question.strip()[:4000]
        if not text:
            query = urlencode({"chat_error": "질문을 입력하세요."})
            return RedirectResponse(f"/screenshots/{screenshot_id}?{query}", status_code=303)
        path = Path(item["file_path"])
        if not path.is_file():
            raise HTTPException(status_code=410, detail="Original screenshot is unavailable")
        history = database.list_chat_messages(screenshot_id)
        try:
            answer = pipeline.provider.chat(path, history, text)
        except ProviderError as exc:
            query = urlencode({"chat_error": str(exc)})
            return RedirectResponse(f"/screenshots/{screenshot_id}?{query}", status_code=303)
        database.add_chat_message(screenshot_id, "user", text)
        database.add_chat_message(screenshot_id, "assistant", answer)
        return RedirectResponse(f"/screenshots/{screenshot_id}#chat", status_code=303)

    @app.post("/screenshots/{screenshot_id}/delete")
    def delete(screenshot_id: int) -> RedirectResponse:
        item = database.get(screenshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Screenshot not found")
        database.delete_screenshot(screenshot_id)
        return RedirectResponse("/", status_code=303)

    @app.post("/screenshots/delete-selected")
    def delete_selected(
        screenshot_ids: Annotated[list[int] | None, Form()] = None,
    ) -> RedirectResponse:
        for screenshot_id in set(screenshot_ids or []):
            database.delete_screenshot(screenshot_id)
        return RedirectResponse("/", status_code=303)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "watching": settings.screenshot_dir is not None,
            "screenshot_directory": str(settings.screenshot_dir)
            if settings.screenshot_dir
            else None,
            "provider": pipeline.provider.name,
        }

    @app.get("/api/screenshots/status")
    def screenshot_statuses() -> list[dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "status": item["status"],
                "title": item.get("title") or Path(item["file_path"]).name,
                "analyzed_at": item.get("analyzed_at"),
            }
            for item in database.list_screenshots(limit=50)
        ]

    return app
