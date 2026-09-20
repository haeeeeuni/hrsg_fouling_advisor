"""감사 로그 조회 (specs/13 §7)."""

from django.urls import include, path
from rest_framework import serializers, viewsets
from rest_framework.routers import DefaultRouter

from accounts.permissions import IsAdminRole
from common.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default="")
    actor_employee_no = serializers.CharField(
        source="actor.employee_no", read_only=True, default=""
    )
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_name",
            "actor_employee_no",
            "action",
            "action_label",
            "target_type",
            "target_id",
            "target_label",
            "before",
            "after",
            "ip",
            "created_at",
        ]
        read_only_fields = fields


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    search_fields = ["target_label", "target_type"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if target_type := params.get("target_type"):
            queryset = queryset.filter(target_type=target_type)
        if action := params.get("action"):
            queryset = queryset.filter(action=action)
        if actor := params.get("actor"):
            queryset = queryset.filter(actor_id=actor)
        if start := params.get("from"):
            queryset = queryset.filter(created_at__gte=start)
        if end := params.get("to"):
            queryset = queryset.filter(created_at__lte=end)
        return queryset


router = DefaultRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [path("", include(router.urls))]
