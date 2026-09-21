"""업로드 테스트 공통 설정. eager 픽스처는 루트 conftest.py 에 있다."""

import pytest


@pytest.fixture(autouse=True)
def isolated_upload_root(settings, tmp_path):
    """업로드 원본은 테스트마다 격리된 임시 경로에 쓴다."""
    settings.UPLOAD_ROOT = tmp_path / "uploads"
    return settings.UPLOAD_ROOT
