from django.urls import path

from common.views_jobs import JobCancelView, JobStatusView

urlpatterns = [
    path("jobs/<str:job_id>/", JobStatusView.as_view(), name="job-status"),
    path("jobs/<str:job_id>/cancel/", JobCancelView.as_view(), name="job-cancel"),
]
