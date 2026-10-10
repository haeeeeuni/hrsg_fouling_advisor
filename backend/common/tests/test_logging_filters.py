"""로그 마스킹 테스트 (specs/13 AC-13-4).

로그에 비밀번호·API 키가 남지 않아야 한다.
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


@pytest.mark.parametrize(
    "secret",
    ["sk-ant-api03-abcdefghijklmnop", "sk-proj-1234567890abcdef", "AIzaSyA1234567890abcdefghijk"],
)
def test_llm_api_keys_are_masked_even_without_field_name(secret):
    masked = mask(f"provider error with {secret} in message")

    assert secret not in masked


def test_api_key_field_is_masked():
    assert "abc123" not in mask("api_key=abc123")


def test_ordinary_text_is_left_alone():
    assert mask("문서 색인이 완료되었습니다.") == "문서 색인이 완료되었습니다."


def test_filter_rewrites_record_message():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="user %s password=%s",
        args=("admin", "qwer"),
        exc_info=None,
    )

    assert MaskSensitiveFilter().filter(record) is True

    message = record.getMessage()
    assert "qwer" not in message
    # args 를 비워 원본이 다른 핸들러에서 다시 살아나지 않게 한다.
    assert record.args == ()
