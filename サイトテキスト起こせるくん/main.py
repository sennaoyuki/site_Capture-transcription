"""エントリーポイント。"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from backend.config import load_config
from frontend.ui import run_app


def main() -> int:
    load_dotenv()
    config = load_config()
    run_app(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())

