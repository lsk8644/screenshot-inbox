from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from screenshot_inbox.providers.openai_compatible import OpenAICompatibleProvider


class FakeResponse:
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "category": "other",
                                "confidence": 0.5,
                                "title": "Fixture",
                                "summary": "Fixture response",
                                "extracted_text": "",
                                "details": {},
                            }
                        )
                    }
                }
            ]
        }
        return json.dumps(response).encode()


class FakeChatResponse(FakeResponse):
    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": "스크린샷에 대한 한국어 답변"}}]}
        ).encode()


def test_provider_requests_compact_json_with_sufficient_output_budget(
    tmp_path: Path, monkeypatch: Any
) -> None:
    image = tmp_path / "fixture.png"
    image.write_bytes(b"fixture")
    captured: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> FakeResponse:
        captured["payload"] = json.loads(request.data or b"{}")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider("https://example.invalid/v1", "secret", "vision", 12)
    result = provider.analyze(image)

    assert result.category == "other"
    assert captured["payload"]["max_tokens"] == 8192
    user_text = captured["payload"]["messages"][1]["content"][0]["text"]
    assert "한국어" in user_text
    assert "정답 코드" in user_text
    system_text = captured["payload"]["messages"][0]["content"]
    assert "natural" in system_text and "Korean" in system_text
    assert "solution_codes" in system_text
    assert "Python, Java, and C++" in system_text
    assert "Volume, Velocity, Variety" in system_text
    assert "term_explanations" in system_text
    assert "Use error" in system_text
    assert captured["timeout"] == 12


def test_provider_chat_sends_image_history_and_korean_instruction(
    tmp_path: Path, monkeypatch: Any
) -> None:
    image = tmp_path / "fixture.png"
    image.write_bytes(b"fixture")
    captured: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> FakeChatResponse:
        captured["payload"] = json.loads(request.data or b"{}")
        return FakeChatResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider("https://example.invalid/v1", "secret", "vision", 12)
    answer = provider.chat(
        image,
        [{"role": "user", "content": "이전 질문"}, {"role": "assistant", "content": "답"}],
        "이 코드를 설명해줘",
    )
    assert answer == "스크린샷에 대한 한국어 답변"
    messages = captured["payload"]["messages"]
    assert "한국어" in messages[0]["content"]
    assert messages[1]["content"] == "이전 질문"
    assert messages[-1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
