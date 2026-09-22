from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Load a small, dependency-free subset of .env syntax without overriding the OS."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


def screenshot_candidates(user_profile: Path | None = None) -> list[Path]:
    profile = user_profile or Path(os.environ.get("USERPROFILE", Path.home()))
    return [
        profile / "Pictures" / "Screenshots",
        profile / "Pictures" / "스크린샷",
        profile / "OneDrive" / "Pictures" / "Screenshots",
        profile / "OneDrive" / "Pictures" / "스크린샷",
        profile / "OneDrive" / "사진" / "Screenshots",
        profile / "OneDrive" / "사진" / "스크린샷",
    ]


def detect_screenshot_dir(
    configured: str | None = None, user_profile: Path | None = None
) -> Path | None:
    if configured:
        path = Path(configured).expanduser()
        return path.resolve() if path.is_dir() else None
    return next(
        (path.resolve() for path in screenshot_candidates(user_profile) if path.is_dir()), None
    )


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def _positive_float(name: str, default: float) -> float:
    try:
        return max(0.05, float(os.environ.get(name, default)))
    except ValueError:
        return default


def _csv_values(name: str) -> tuple[str, ...]:
    return tuple(value for raw in os.environ.get(name, "").split(",") if (value := raw.strip()))


def _positive_float_values(name: str, default: tuple[float, ...]) -> tuple[float, ...]:
    raw_values = _csv_values(name)
    if not raw_values:
        return default
    try:
        return tuple(max(0.05, float(value)) for value in raw_values)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    data_dir: Path
    database_path: Path
    screenshot_dir: Path | None
    screenshot_dir_configured: str | None
    ai_provider: str
    ai_api_key: str | None
    ai_base_url: str
    ai_model: str | None
    ai_fallback_models: tuple[str, ...]
    ai_timeout_seconds: float
    max_analysis_attempts: int
    analysis_retry_delays_seconds: tuple[float, ...]
    stable_interval_seconds: float
    stable_checks: int
    host: str
    port: int

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> Settings:
        root = (project_root or Path.cwd()).resolve()
        load_dotenv(root / ".env")
        configured = os.environ.get("SCREENSHOT_DIR") or None
        raw_data_dir = Path(os.environ.get("DATA_DIR", "./data")).expanduser()
        data_dir = raw_data_dir if raw_data_dir.is_absolute() else root / raw_data_dir
        return cls(
            project_root=root,
            data_dir=data_dir.resolve(),
            database_path=(data_dir / "screenshot_inbox.db").resolve(),
            screenshot_dir=detect_screenshot_dir(configured),
            screenshot_dir_configured=configured,
            ai_provider=os.environ.get("AI_PROVIDER", "mock").strip().lower(),
            ai_api_key=os.environ.get("AI_API_KEY") or None,
            ai_base_url=os.environ.get("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            ai_model=os.environ.get("AI_MODEL") or None,
            ai_fallback_models=_csv_values("AI_FALLBACK_MODELS"),
            ai_timeout_seconds=_positive_float("AI_TIMEOUT_SECONDS", 60.0),
            max_analysis_attempts=_positive_int("MAX_ANALYSIS_ATTEMPTS", 3),
            analysis_retry_delays_seconds=_positive_float_values(
                "ANALYSIS_RETRY_DELAYS_SECONDS", (60.0, 300.0, 900.0)
            ),
            stable_interval_seconds=_positive_float("FILE_STABLE_INTERVAL_SECONDS", 0.5),
            stable_checks=_positive_int("FILE_STABLE_CHECKS", 3),
            host=os.environ.get("HOST", "127.0.0.1"),
            port=_positive_int("PORT", 8765),
        )
