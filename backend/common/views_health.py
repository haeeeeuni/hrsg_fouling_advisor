"""헬스체크 (specs/18 §3, §7).

컨테이너·로드밸런서가 기동 여부를 판단하는 용도라 **인증 없이** 열어 둔다.
그 대신 내부 구성이 드러나지 않도록 버전·경로·예외 메시지를 담지 않는다.
"""

from __future__ import annotations

from django.db import connection
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class LivenessView(APIView):
    """프로세스가 살아 있는가. 의존 서비스는 보지 않는다.

    DB 가 잠깐 끊겼다고 컨테이너를 재시작하면 상황이 더 나빠지므로 분리한다.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadinessView(APIView):
    """요청을 받을 준비가 됐는가. DB 연결까지 확인한다."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        checks = {"database": _check_database()}
        healthy = all(checks.values())
        return Response(
            {"status": "ok" if healthy else "unavailable", "checks": checks},
            status=(
                http_status.HTTP_200_OK if healthy else http_status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:  # noqa: BLE001 - 원인은 로그로 남기고 응답에는 노출하지 않는다.
        return False
