from django.urls import path

from common.views_health import LivenessView, ReadinessView
from common.views_jobs import JobCancelView, JobStatusView

urlpatterns = [
    # 헬스체크는 인증 없이 열려 있다 (specs/18 §7 — 컨테이너·LB 용)
    path("health/live/", LivenessView.as_view(), name="health-live"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    path("jobs/<str:job_id>/", JobStatusView.as_view(), name="job-status"),
    path("jobs/<str:job_id>/cancel/", JobCancelView.as_view(), name="job-cancel"),
]
