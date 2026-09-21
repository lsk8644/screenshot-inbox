from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def image_path(tmp_path: Path) -> Path:
    path = tmp_path / "problem-example.png"
    Image.new("RGB", (40, 30), color=(20, 40, 60)).save(path)
    return path
