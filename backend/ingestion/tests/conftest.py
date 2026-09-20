"""업로드 테스트 공통 설정.

Celery 워커 없이 태스크를 즉시 실행한다. Django 설정만 바꾸면 이미 생성된 Celery 앱에
반영되지 않으므로 앱 conf 를 직접 건드린다.
"""

import pytest
from celery import current_app


@pytest.fixture(autouse=True)
def celery_eager(settings, tmp_path):
    previous = (current_app.conf.task_always_eager, current_app.conf.task_eager_propagates)
    current_app.conf.task_always_eager = True
    current_app.conf.task_eager_propagates = True
    # 업로드 원본은 테스트마다 격리된 임시 경로에 쓴다.
    settings.UPLOAD_ROOT = tmp_path / "uploads"
    yield
    current_app.conf.task_always_eager, current_app.conf.task_eager_propagates = previous
