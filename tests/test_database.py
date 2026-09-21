from __future__ import annotations

from pathlib import Path

from screenshot_inbox.database import ScreenshotDatabase


def test_insert_duplicate_and_persistence(tmp_path: Path) -> None:
    path = tmp_path / "inbox.db"
    database = ScreenshotDatabase(path)
    database.initialize()
    first_id, inserted = database.insert_screenshot(tmp_path / "a.png", "same", "2026-01-01")
    duplicate_id, duplicate_inserted = database.insert_screenshot(
        tmp_path / "b.png", "same", "2026-01-02"
    )
    assert inserted is True
    assert duplicate_inserted is False
    assert duplicate_id == first_id
    reopened = ScreenshotDatabase(path)
    assert reopened.get(first_id) is not None


def test_status_updates(tmp_path: Path) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(tmp_path / "a.png", "hash", "2026-01-01")
    database.mark_analyzing(screenshot_id, "mock", "test")
    assert database.get(screenshot_id)["status"] == "analyzing"  # type: ignore[index]
    database.mark_completed(
        screenshot_id,
        {
            "category": "other",
            "confidence": 0.2,
            "title": "A",
            "summary": "B",
            "extracted_text": "",
            "details": {},
        },
    )
    record = database.get(screenshot_id)
    assert record is not None
    assert record["status"] == "completed"
    assert record["analysis"]["title"] == "A"
    assert database.reset_for_retry(screenshot_id) is True
    assert database.get(screenshot_id)["status"] == "pending"  # type: ignore[index]


def test_failed_items_are_in_error_filter(tmp_path: Path) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(tmp_path / "failed.png", "failed", "2026")
    database.mark_failed(screenshot_id, "provider failed", 3)
    assert [item["id"] for item in database.list_screenshots("error")] == [screenshot_id]


def test_chat_and_record_deletion_preserve_original_file(tmp_path: Path) -> None:
    image = tmp_path / "keep.png"
    image.write_bytes(b"original")
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(image, "keep", "2026")
    database.add_chat_message(screenshot_id, "user", "질문")
    database.add_chat_message(screenshot_id, "assistant", "답변")
    assert [message["content"] for message in database.list_chat_messages(screenshot_id)] == [
        "질문",
        "답변",
    ]
    assert database.delete_screenshot(screenshot_id) is True
    assert database.get(screenshot_id) is None
    assert image.is_file()


def test_saved_mapping_strings_are_normalized_when_read(tmp_path: Path) -> None:
    database = ScreenshotDatabase(tmp_path / "inbox.db")
    database.initialize()
    screenshot_id, _ = database.insert_screenshot(tmp_path / "lecture.png", "lecture", "2026")
    database.mark_completed(
        screenshot_id,
        {
            "category": "lecture",
            "confidence": 0.8,
            "title": "Amdahl",
            "summary": "설명",
            "extracted_text": "",
            "details": {
                "term_explanations": ["{'Speedup': '개선 전후의 성능 비율입니다.'}"]
            },
        },
    )
    record = database.get(screenshot_id)
    assert record is not None
    assert record["analysis"]["details"]["term_explanations"] == [
        "Speedup — 개선 전후의 성능 비율입니다."
    ]
