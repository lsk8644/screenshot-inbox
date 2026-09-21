from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, cast

Category = Literal["error", "problem", "lecture", "notice", "code", "document", "other"]
CATEGORIES: tuple[Category, ...] = (
    "error",
    "problem",
    "lecture",
    "notice",
    "code",
    "document",
    "other",
)


class AnalysisValidationError(ValueError):
    pass


DETAIL_DEFAULTS: dict[Category, dict[str, Any]] = {
    "error": {
        "application": "",
        "error_message": "",
        "possible_causes": [],
        "recommended_steps": [],
    },
    "problem": {
        "subject": "",
        "question": "",
        "choices": [],
        "answer": "",
        "explanation": "",
        "concepts": [],
        "uncertainty": "",
    },
    "lecture": {
        "topic": "",
        "key_points": [],
        "important_terms": [],
        "term_explanations": [],
        "study_notes": [],
    },
    "notice": {
        "organization": "",
        "event_name": "",
        "deadline": "",
        "eligibility": "",
        "requirements": [],
        "actions": [],
    },
    "code": {
        "language": "",
        "purpose": "",
        "approach": "",
        "solution_codes": {"python": "", "java": "", "cpp": ""},
        "issues": [],
        "explanation": "",
        "complexity": "",
        "suggested_changes": [],
    },
    "document": {"document_type": "", "key_points": [], "important_values": []},
    "other": {},
}


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    category: Category
    confidence: float
    title: str
    summary: str
    extracted_text: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "title": self.title,
            "summary": self.summary,
            "extracted_text": self.extracted_text,
            "details": self.details,
        }


def _object_from_text(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start : end + 1])
            except json.JSONDecodeError as nested:
                raise AnalysisValidationError("Model response was not valid JSON") from nested
        else:
            raise AnalysisValidationError("Model response was not valid JSON") from exc
    if not isinstance(value, dict):
        raise AnalysisValidationError("Model response must be a JSON object")
    return cast(dict[str, Any], value)


def parse_analysis(value: str | dict[str, Any]) -> AnalysisResult:
    payload = _object_from_text(value) if isinstance(value, str) else value
    raw_category = str(payload.get("category", "other")).lower().strip()
    category: Category = raw_category if raw_category in CATEGORIES else "other"
    if category == "other":
        visible_text = " ".join(
            str(payload.get(key, "")) for key in ("title", "summary", "extracted_text")
        )
        error_pattern = re.compile(
            r"\b(error|exception|traceback|fatal|crash(?:ed)?|failed|failure|"
            r"cannot|unable to|access denied|not found|timed? out)\b|오류|에러|예외|실패|"
            r"접근.?거부|찾을 수 없|응답.?없",
            re.IGNORECASE,
        )
        if error_pattern.search(visible_text):
            category = "error"
    try:
        confidence = min(1.0, max(0.0, float(payload.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    details = payload.get("details", {})
    if not isinstance(details, dict):
        details = {}
    normalized_details: dict[str, Any] = {}
    for key, default in DETAIL_DEFAULTS[category].items():
        item = details.get(key, default)
        if isinstance(default, list) and not isinstance(item, list):
            item = [str(item)] if item else []
        elif isinstance(default, dict):
            source = item if isinstance(item, dict) else {}
            item = {name: str(source.get(name, "")) for name in default}
        elif isinstance(default, str) and not isinstance(item, str):
            item = str(item) if item is not None else ""
        normalized_details[key] = item
    title = str(payload.get("title", "")).strip() or "Untitled screenshot"
    return AnalysisResult(
        category=category,
        confidence=confidence,
        title=title[:300],
        summary=str(payload.get("summary", "")).strip(),
        extracted_text=str(payload.get("extracted_text", "")).strip(),
        details=normalized_details,
    )
