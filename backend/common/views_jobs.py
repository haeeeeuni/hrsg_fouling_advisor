"""작업 상태 폴링 (specs/10 §7). 권한은 기본값(IsApprovedUser)."""

from rest_framework import status as http_status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common import jobs


class JobStatusView(APIView):
    def get(self, request: Request, job_id: str) -> Response:
        return Response(jobs.get_status(job_id))


class JobCancelView(APIView):
    def post(self, request: Request, job_id: str) -> Response:
        jobs.cancel(job_id)
        return Response(
            {"job_id": job_id, "status": jobs.CANCELED},
            status=http_status.HTTP_202_ACCEPTED,
        )
