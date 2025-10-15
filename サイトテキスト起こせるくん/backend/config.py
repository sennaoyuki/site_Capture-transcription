"""アプリケーション設定のデータモデルとユーティリティ。"""

from __future__ import annotations

import dataclasses
import datetime as dt
import os
from pathlib import Path


DEFAULT_SLICE_HEIGHT = 2000
DEFAULT_MODEL_NAME = "gemini-pro-vision"


@dataclasses.dataclass(slots=True)
class AppConfig:
    """全体設定を表現するデータクラス。"""

    output_root: Path
    slice_height: int = DEFAULT_SLICE_HEIGHT
    model_name: str = DEFAULT_MODEL_NAME
    request_timeout: int = 90
    max_retries: int = 3
    retry_backoff_base: float = 2.0

    @property
    def timestamp_prefix(self) -> str:
        return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_config(output_dir: str | None = None) -> AppConfig:
    """環境変数を考慮して設定を読み込む。"""

    base_output = Path(output_dir or os.environ.get("SITE_TRANSCRIBER_OUTPUT", "outputs"))
    base_output.mkdir(parents=True, exist_ok=True)
    slice_height = int(os.environ.get("SITE_TRANSCRIBER_SLICE_HEIGHT", DEFAULT_SLICE_HEIGHT))
    model_name = os.environ.get("SITE_TRANSCRIBER_MODEL", DEFAULT_MODEL_NAME)
    request_timeout = int(os.environ.get("SITE_TRANSCRIBER_TIMEOUT", 90))
    max_retries = int(os.environ.get("SITE_TRANSCRIBER_MAX_RETRIES", 3))
    retry_backoff_base = float(os.environ.get("SITE_TRANSCRIBER_RETRY_BACKOFF", 2.0))

    return AppConfig(
        output_root=base_output,
        slice_height=slice_height,
        model_name=model_name,
        request_timeout=request_timeout,
        max_retries=max_retries,
        retry_backoff_base=retry_backoff_base,
    )
