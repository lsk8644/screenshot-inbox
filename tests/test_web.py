from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from screenshot_inbox.config import Settings
from screenshot_inbox.database import ScreenshotDatabase
from screenshot_inbox.pipeline import AnalysisPipeline, sha256_file
from screenshot_inbox.providers.mock import MockProvider
from screenshot_inbox.web import _with_seoul_timestamps, create_app, render_markdown


def make_settings(root: Path, database_path: Path) -> Settings:
    return Settings(
        project_root=root,
        data_dir=database_path.parent,
        database_path=database_path,
        screenshot_dir=None,
        screenshot_dir_configured=None,
        ai_provider="mock",
        ai_api_key=None,
        ai_base_url="https://example.invalid/v1",
        ai_model=None,
        ai_timeout_seconds=1,
        max_analysis_attempts=3,
        stable_interval_seconds=0.01,
        stable_checks=1,
        host="127.0.0.1",
        port=8765,
    )


def test_inbox_detail_image_and_health(
    tmp_path: Path, image_path: Path, project_root: Path = Path(__file__).parents[1]
) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(image_path, sha256_file(image_path), "2026-01-01")
    pipeline = AnalysisPipeline(database, MockProvider())
    pipeline.process_now(screenshot_id)
    app = create_app(make_settings(project_root, database.path), database, pipeline)
    client = TestClient(app)
    assert client.get("/").status_code == 200
    inbox_html = client.get("/").text
    assert "Screenshot Inbox" in inbox_html
    assert "Watching" in inbox_html
    assert 'class="provider-label"' not in inbox_html
    assert 'class="directory"' not in inbox_html
    assert 'class="file-name"' not in inbox_html
    detail_html = client.get(f"/screenshots/{screenshot_id}").text
    assert str(image_path.parent) not in detail_html
    assert "<p title=" not in detail_html
    assert client.get(f"/screenshots/{screenshot_id}/image").status_code == 200
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["watching"] is False
    statuses = client.get("/api/screenshots/status").json()
    assert statuses == [
        {
            "id": screenshot_id,
            "status": "completed",
            "title": image_path.stem.replace("_", " ").replace("-", " ").strip().title(),
            "analyzed_at": statuses[0]["analyzed_at"],
        }
    ]
    assert 'id="toast-region"' in inbox_html
    script = client.get("/static/app.js").text
    assert "sessionStorage" in script
    assert "screenshotInboxStatusesV2" in script
    assert "analyzed_at" in script
    assert "refreshTimeline" in script
    assert "DOMParser" in script
    assert "1500" in script


def test_timeline_uses_seoul_date_and_24_hour_time() -> None:
    items = _with_seoul_timestamps(
        [
            {"detected_at": "2026-09-21 15:05:00"},
            {"detected_at": "2026-09-21 14:59:00"},
        ]
    )
    assert items[0]["date_label"] == "9.22"
    assert items[0]["time_label"] == "00:05"
    assert items[1]["date_label"] == "9.21"
    assert items[1]["time_label"] == "23:59"


def test_chat_markdown_is_formatted_and_html_is_escaped() -> None:
    rendered = str(
        render_markdown(
            "## 풀이\n**중요** 및 `value`\n- 첫 단계\n```python\nprint('<script>')\n```"
        )
    )
    assert "<h4>풀이</h4>" in rendered
    assert "<strong>중요</strong>" in rendered
    assert "<ul>" in rendered and "<li>첫 단계</li>" in rendered
    assert 'class="language-python"' in rendered
    assert "&lt;script&gt;" in rendered
    assert "<script>" not in rendered


def test_chat_code_tabs_and_delete_keep_original(
    tmp_path: Path, image_path: Path, project_root: Path = Path(__file__).parents[1]
) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(image_path, sha256_file(image_path), "2026")
    database.mark_completed(
        screenshot_id,
        {
            "category": "code",
            "confidence": 0.9,
            "title": "코딩 문제",
            "summary": "세 언어 풀이",
            "extracted_text": "hidden source",
            "details": {
                "solution_codes": {
                    "python": "print(1)",
                    "java": "class Main {}",
                    "cpp": "int main() {}",
                }
            },
        },
    )
    pipeline = AnalysisPipeline(database, MockProvider())
    client = TestClient(create_app(make_settings(project_root, database.path), database, pipeline))
    detail = client.get(f"/screenshots/{screenshot_id}").text
    assert 'data-code-tab="python"' in detail
    assert 'data-code-tab="java"' in detail
    assert 'data-code-tab="cpp"' in detail
    assert "인식된 원문" not in detail
    assert "한국어로 다시 분석" not in detail
    assert "풀이의 특정 단계" not in detail
    assert "예: 이 코드의 시간 복잡도" not in detail

    response = client.post(
        f"/screenshots/{screenshot_id}/chat",
        data={"question": "설명해줘"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Mock 답변: 설명해줘" in client.get(f"/screenshots/{screenshot_id}").text

    response = client.post(f"/screenshots/{screenshot_id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert database.get(screenshot_id) is None
    assert image_path.is_file()


def test_bulk_select_and_delete_preserve_originals(
    tmp_path: Path, image_path: Path, project_root: Path = Path(__file__).parents[1]
) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    first_id, _ = database.insert_screenshot(
        image_path, sha256_file(image_path), "2026-01-01T00:00:00+00:00"
    )
    second_path = tmp_path / "second.png"
    second_path.write_bytes(image_path.read_bytes())
    second_id, _ = database.insert_screenshot(
        second_path, "different-hash", "2026-01-02T00:00:00+00:00"
    )
    pipeline = AnalysisPipeline(database, MockProvider())
    client = TestClient(create_app(make_settings(project_root, database.path), database, pipeline))

    inbox = client.get("/").text
    assert 'id="inbox-menu-button"' in inbox
    assert 'id="inbox-menu-popover" hidden' in inbox
    assert 'class="selection-toolbar"' in inbox
    assert 'method="post" hidden' in inbox
    assert 'id="select-all-screenshots"' in inbox
    assert inbox.count('class="select-item"') == 2
    assert 'class="delete-form"' not in inbox
    script = client.get("/static/app.js").text
    assert "enter-selection-mode" in script
    assert "selection-mode" in script
    assert '"Escape"' in script
    response = client.post(
        "/screenshots/delete-selected",
        data={"screenshot_ids": [str(first_id), str(second_id)]},        follow_redirects=False,
    )

    assert response.status_code == 303
    assert database.list_screenshots() == []
    assert image_path.is_file()
    assert second_path.is_file()
