from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from screenshot_inbox.providers.base import ProviderError
from screenshot_inbox.schemas import AnalysisResult, parse_analysis

SYSTEM_PROMPT = """You analyze screenshots for a private local inbox. Return JSON only.
Write title, summary, explanations, recommendations, answers, and every details value in natural
Korean, even when the screenshot is in another language. Preserve source code, identifiers, and
extracted_text in their original language where appropriate.
Use exactly one category: error, problem, lecture, notice, code, document, other.
Use error when the main content is an exception, stack trace, error dialog, error code, failed
operation, crash, or broken application state. Use code for programming exercises, algorithm
questions, and requests to write, review, or fix source code. For a programming problem, solve it
completely with runnable Python, Java, and C++ solutions in solution_codes, plus a Korean approach,
explanation, and time/space complexity. Never invent unreadable constraints, inputs, dates, or
answers; state uncertainty.
For lectures, articles, and other educational material, go beyond restating visible text. Expand
every acronym or named framework, define each component in plain Korean, explain why it matters,
and give a concrete example. When 3V or 5V appears, explicitly explain Volume, Velocity, Variety,
Veracity, and Value and how 5V extends 3V.
Required common fields: category, confidence (0..1), title, summary, extracted_text, details.
Details schema:
error: application, error_message, possible_causes[], recommended_steps[]
problem: subject, question, choices[], answer, explanation, concepts[], uncertainty
lecture: topic, key_points[], important_terms[], term_explanations[], study_notes[]
notice: organization, event_name, deadline, eligibility, requirements[], actions[]
code: purpose, approach, solution_codes{python,java,cpp}, explanation,
complexity, issues[], suggested_changes[]
document: document_type, key_points[], important_values[]
other: {}"""

CODE_ONLY_PROMPT = """The screenshot is a programming problem. The top-level category value must
be the exact string "code"; do not create a category_code key.
Solve the general problem, not merely the visible sample. Return runnable and complete Python,
Java, and C++ implementations under details.solution_codes, plus Korean purpose, approach,
explanation, complexity, issues, and suggested_changes. Do not return a language field.
Preserve the original problem statement in extracted_text. Return one JSON object without
Markdown, using exactly this shape:
{"category":"code","confidence":0.0,"title":"","summary":"","extracted_text":"",
"details":{"purpose":"","approach":"","solution_codes":{"python":"","java":"","cpp":""},
"explanation":"","complexity":"","issues":[],"suggested_changes":[]}}"""

PROGRAMMING_MARKERS = (
    "codeforces",
    "atcoder",
    "leetcode",
    "baekjoon",
    "time limit per test",
    "memory limit per test",
    "competitive programming",
)


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model: str | None = model
        self.timeout = timeout

    def _complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body: Any = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            retryable = status in {429, 500, 502, 503}
            if status in {400, 404, 415, 422}:
                message = (
                    "Provider rejected the image or model request; "
                    "verify vision support and model name"
                )
            else:
                message = f"Provider HTTP error {status}"
            raise ProviderError(message, retryable=retryable, status_code=status) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(
                "Provider connection timed out or is unavailable", retryable=True
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProviderError("Provider returned an unreadable response") from exc
        if not isinstance(body, dict):
            raise ProviderError("Provider returned an unreadable response")
        return body

    @staticmethod
    def _message_text(body: dict[str, Any]) -> str:
        try:
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(
                    str(part.get("text", "")) for part in content if isinstance(part, dict)
                )
            text = str(content).strip()
            if not text:
                raise ValueError("empty content")
            return text
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError(f"Provider response was malformed: {exc}") from exc

    @staticmethod
    def _looks_like_programming_problem(result: AnalysisResult) -> bool:
        if result.category == "code":
            return True
        if result.category != "problem":
            return False
        visible_text = " ".join(
            (result.title, result.summary, result.extracted_text)
        ).lower()
        if any(marker in visible_text for marker in PROGRAMMING_MARKERS):
            return True
        section_markers = sum(
            marker in visible_text
            for marker in ("\ninput\n", "\noutput\n", "constraints", "example input")
        )
        return section_markers >= 2

    @staticmethod
    def _has_complete_solution_codes(result: AnalysisResult) -> bool:
        codes = result.details.get("solution_codes")
        return isinstance(codes, dict) and all(
            isinstance(codes.get(language), str) and codes[language].strip()
            for language in ("python", "java", "cpp")
        )

    def _parse_analysis_body(self, body: dict[str, Any]) -> AnalysisResult:
        try:
            return parse_analysis(self._message_text(body))
        except ValueError as exc:
            raise ProviderError(
                f"Provider response was malformed: {exc}",
                retryable=True,
            ) from exc

    def _parse_code_repair_body(
        self, body: dict[str, Any], fallback: AnalysisResult
    ) -> AnalysisResult:
        text = self._message_text(body)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return self._parse_analysis_body(body)
        if not isinstance(payload, dict):
            return self._parse_analysis_body(body)

        details = payload.get("details")
        if not isinstance(details, dict):
            detail_names = (
                "purpose",
                "approach",
                "solution_codes",
                "explanation",
                "complexity",
                "issues",
                "suggested_changes",
            )
            details = {name: payload.get(name) for name in detail_names if name in payload}
        normalized = {
            "category": "code",
            "confidence": payload.get("confidence", fallback.confidence),
            "title": payload.get("title") or fallback.title,
            "summary": payload.get("summary") or fallback.summary,
            "extracted_text": payload.get("extracted_text") or fallback.extracted_text,
            "details": details,
        }
        return parse_analysis(normalized)

    def analyze(self, image_path: Path) -> AnalysisResult:
        mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "이 스크린샷을 분석하세요. 설명과 답변은 한국어로 작성하고, "
                                "프로그래밍 문제라면 Python, Java, C++ 정답 코드와 "
                                "일반 입력 전체를 처리하는 풀이를 포함하세요. 예제 출력만 "
                                "하드코딩하지 마세요. "
                                "마크다운 없이 하나의 간결한 JSON 객체만 반환하세요."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{encoded}"},
                        },
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 8192,
        }
        body = self._complete(payload)
        result = self._parse_analysis_body(body)
        if not self._looks_like_programming_problem(result):
            return result
        if result.category == "code" and self._has_complete_solution_codes(result):
            return result

        payload["messages"] = [
            {"role": "system", "content": CODE_ONLY_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "이 프로그래밍 문제를 완전히 풀고 한국어로 설명하세요. "
                            "Python, Java, C++ 정답 코드를 모두 반환하세요."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    },
                ],
            },
        ]
        corrected = self._parse_code_repair_body(self._complete(payload), result)
        if corrected.category != "code" or not self._has_complete_solution_codes(corrected):
            raise ProviderError(
                "Provider omitted one or more required programming solutions",
                retryable=True,
            )
        return corrected

    def chat(self, image_path: Path, history: list[dict[str, Any]], question: str) -> str:
        mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "사용자가 첨부한 스크린샷에 관해 대화하세요. 항상 자연스러운 한국어로 "
                    "답하고, 코딩 질문에는 실행 가능한 코드와 근거를 제공하세요. 화면에서 "
                    "읽을 수 없는 내용은 추측하지 마세요."
                ),
            }
        ]
        for message in history[-12:]:
            role = str(message.get("role", ""))
            content = str(message.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    },
                ],
            }
        )
        body = self._complete(
            {
                "model": self.model,
                "temperature": 0.2,
                "messages": messages,
                "max_tokens": 2048,
            }
        )
        return self._message_text(body)
