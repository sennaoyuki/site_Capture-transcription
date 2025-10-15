"""共通ユーティリティ。"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9-_]+")


def slugify(value: str, length: int = 60) -> str:
    slug = SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return slug[:length] or "site"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def encode_image(path: Path) -> dict[str, str]:
    with path.open("rb") as fp:
        data = base64.b64encode(fp.read()).decode("utf-8")
    mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return {"mime_type": mime_type, "data": data}


@dataclass
class TranscriptResult:
    url: str
    output_dir: Path
    text_output: Path
    image_files: Iterable[Path]
    text_content: str

