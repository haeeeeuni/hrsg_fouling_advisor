"""로그 마스킹 테스트 (AC-18-3).

로그에 비밀번호·전체 사번이 남지 않아야 한다.
"""

import logging

import pytest

from common.logging_filters import MaskSensitiveFilter, mask


@pytest.mark.parametrize(
    "text",
    [
        "login attempt password=qwer1234",
        'payload {"password": "qwer1234"}',
        "current_password=abcd new_password=efgh",
    ],
)
def test_password_values_are_masked(text):
    masked = mask(text)

    assert "qwer1234" not in masked
    assert "abcd" not in masked
    assert "efgh" not in masked
    assert "***" in masked


def test_employee_no_is_partially_masked():
    masked = mask("login failed for ADM01")

    assert "ADM01" not in masked
    assert "AD***" in masked


def test_ordinary_text_is_left_alone():
    assert mask("분석 실행이 완료되었습니다.") == "분석 실행이 완료되었습니다."


def test_filter_rewrites_record_message():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="user %s password=%s",
        args=("ADM01", "qwer"),
        exc_info=None,
    )

    assert MaskSensitiveFilter().filter(record) is True

    message = record.getMessage()
    assert "qwer" not in message
    assert "ADM01" not in message
    # args 를 비워 원본이 다른 핸들러에서 다시 살아나지 않게 한다.
    assert record.args == ()
