#!/usr/bin/env python
"""Django 관리 명령 진입점."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Django를 불러올 수 없습니다. 가상환경이 활성화되어 있고 "
            "`pip install -r requirements.txt`가 완료되었는지 확인하세요."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
