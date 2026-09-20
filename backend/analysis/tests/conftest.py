"""분석 테스트 공통 설정."""

import pytest
from celery import current_app


@pytest.fixture(autouse=True)
def celery_eager():
    """Celery 워커 없이 태스크를 즉시 실행한다."""
    previous = (current_app.conf.task_always_eager, current_app.conf.task_eager_propagates)
    current_app.conf.task_always_eager = True
    current_app.conf.task_eager_propagates = True
    yield
    current_app.conf.task_always_eager, current_app.conf.task_eager_propagates = previous
