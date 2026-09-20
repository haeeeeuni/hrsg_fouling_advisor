"""작업 상태 폴링 (specs/15 §1)."""

from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common import jobs


class JobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, job_id: str) -> Response:
        return Response(jobs.get_status(job_id))


class JobCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, job_id: str) -> Response:
        jobs.cancel(job_id)
        return Response(
            {"job_id": job_id, "status": jobs.CANCELED},
            status=http_status.HTTP_202_ACCEPTED,
        )
