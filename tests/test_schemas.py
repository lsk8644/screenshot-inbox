from __future__ import annotations

import pytest

from screenshot_inbox.schemas import AnalysisValidationError, parse_analysis


def test_category_and_details_are_normalized() -> None:
    result = parse_analysis(
        {
            "category": "problem",
            "confidence": 4,
            "title": "Question",
            "summary": "A database problem",
            "details": {"concepts": "normalization", "answer": None},
        }
    )
    assert result.category == "problem"
    assert result.confidence == 1.0
    assert result.details["concepts"] == ["normalization"]
    assert result.details["answer"] == ""


def test_fenced_json_is_accepted() -> None:
    result = parse_analysis('```json\n{"category":"notice","title":"Deadline"}\n```')
    assert result.category == "notice"


def test_malformed_model_response_is_controlled() -> None:
    with pytest.raises(AnalysisValidationError):
        parse_analysis("not json")


def test_unknown_category_falls_back_to_other() -> None:
    assert parse_analysis({"category": "invoice", "title": "Invoice"}).category == "other"


def test_code_solution_fields_are_normalized() -> None:
    result = parse_analysis(
        {
            "category": "code",
            "title": "배열 합 구하기",
            "details": {
                "language": "Python",
                "solution_codes": {
                    "python": "print(sum(values))",
                    "java": "System.out.println(sum);",
                },
            },
        }
    )
    assert result.details["solution_codes"]["python"] == "print(sum(values))"
    assert result.details["solution_codes"]["java"] == "System.out.println(sum);"
    assert result.details["solution_codes"]["cpp"] == ""
    assert result.details["approach"] == ""
    assert result.details["complexity"] == ""


def test_visible_error_text_corrects_other_category() -> None:
    result = parse_analysis(
        {
            "category": "other",
            "title": "애플리케이션 오류",
            "summary": "작업이 실패했습니다.",
            "extracted_text": "PermissionError: access denied",
        }
    )
    assert result.category == "error"
    assert "recommended_steps" in result.details


def test_lecture_term_explanations_are_normalized() -> None:
    result = parse_analysis(
        {
            "category": "lecture",
            "title": "빅데이터의 5V",
            "details": {"term_explanations": "Volume은 데이터의 규모입니다."},
        }
    )
    assert result.details["term_explanations"] == ["Volume은 데이터의 규모입니다."]


def test_mapping_entries_and_saved_mapping_strings_are_flattened() -> None:
    result = parse_analysis(
        {
            "category": "lecture",
            "title": "성능 법칙",
            "details": {
                "term_explanations": [
                    {"Amdahl's Law": "순차 영역이 전체 성능 향상의 병목이 됩니다."},
                    "{'Speedup': '개선 전후의 성능 비율입니다.'}",
                ]
            },
        }
    )
    assert result.details["term_explanations"] == [
        "Amdahl's Law: 순차 영역이 전체 성능 향상의 병목이 됩니다.",
        "Speedup: 개선 전후의 성능 비율입니다.",
    ]


def test_term_explanation_object_becomes_one_readable_line() -> None:
    result = parse_analysis(
        {
            "category": "lecture",
            "title": "Pthreads",
            "details": {
                "term_explanations": [
                    {"term": "Pthreads", "explanation": "POSIX 표준 스레드 API입니다."}
                ]
            },
        }
    )
    assert result.details["term_explanations"] == ["Pthreads: POSIX 표준 스레드 API입니다."]


def test_labeled_lines_and_em_dash_entries_use_term_colon_explanation() -> None:
    result = parse_analysis(
        {
            "category": "lecture",
            "title": "Pthreads",
            "details": {
                "term_explanations": [
                    "term — Pthreads",
                    "explanation — POSIX 표준 스레드 API입니다.",
                    "Speedup — 개선 전후의 성능 비율입니다.",
                ]
            },
        }
    )
    assert result.details["term_explanations"] == [
        "Pthreads: POSIX 표준 스레드 API입니다.",
        "Speedup: 개선 전후의 성능 비율입니다.",
    ]
