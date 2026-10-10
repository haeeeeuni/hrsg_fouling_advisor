"""Celery 앱 (specs/13 §6).

오래 걸리는 작업(문서 색인·가져오기)은 워커에서 실행하고,
뷰는 202 + job_id 를 즉시 돌려준다(specs/10 §1).
"""

import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("hrsg")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
