from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from screenshot_inbox.providers.base import ProviderError
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


class AnalysisResponse(FakeResponse):
    def __init__(self, analysis: dict[str, Any]) -> None:
        self.analysis = analysis

    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": json.dumps(self.analysis, ensure_ascii=False)}}]}
        ).encode()


class InvalidAnalysisResponse(FakeResponse):
    def read(self) -> bytes:
        return json.dumps({"choices": [{"message": {"content": "{not valid json"}}]}).encode()


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


def test_provider_repairs_misclassified_programming_problem(
    tmp_path: Path, monkeypatch: Any
) -> None:
    image = tmp_path / "problem.png"
    image.write_bytes(b"fixture")
    responses = [
        {
            "category": "problem",
            "confidence": 0.9,
            "title": "Codeforces A. Example",
            "summary": "알고리즘 문제",
            "extracted_text": "time limit per test\nInput\n1\nOutput\n1",
            "details": {"answer": "1", "explanation": "설명"},
        },
        {
            "category_code": "code",
            "extracted_text": "time limit per test",
            "purpose": "문제 풀이",
            "approach": "일반 입력을 처리한다.",
            "solution_codes": {
                "python": "print(input())",
                "java": "class Main {}",
                "cpp": "int main() {}",
            },
        },
    ]
    payloads: list[dict[str, Any]] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> AnalysisResponse:
        payloads.append(json.loads(request.data or b"{}"))
        return AnalysisResponse(responses.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider("https://example.invalid/v1", "secret", "vision", 12)

    result = provider.analyze(image)

    assert result.category == "code"
    assert result.details["solution_codes"]["python"] == "print(input())"
    assert len(payloads) == 2
    assert "top-level category value" in payloads[1]["messages"][0]["content"]


def test_provider_marks_malformed_analysis_as_retryable(tmp_path: Path, monkeypatch: Any) -> None:
    image = tmp_path / "problem.png"
    image.write_bytes(b"fixture")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: InvalidAnalysisResponse(),
    )
    provider = OpenAICompatibleProvider("https://example.invalid/v1", "secret", "vision", 12)

    with pytest.raises(ProviderError) as error:
        provider.analyze(image)

    assert error.value.retryable is True


def test_provider_uses_fallback_model_after_retryable_error(
    tmp_path: Path, monkeypatch: Any
) -> None:
    image = tmp_path / "fixture.png"
    image.write_bytes(b"fixture")
    requested_models: list[str] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> FakeResponse:
        payload = json.loads(request.data or b"{}")
        requested_models.append(payload["model"])
        if payload["model"] == "primary":
            raise urllib.error.HTTPError(
                request.full_url,
                503,
                "Service Unavailable",
                {},
                io.BytesIO(b'{"error":{"message":"high demand"}}'),
            )
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        "https://example.invalid/v1",
        "secret",
        "primary",
        12,
        fallback_models=("backup",),
    )

    result = provider.analyze(image)

    assert result.category == "other"
    assert requested_models == ["primary", "backup"]
    assert provider.last_model_used == "backup"
