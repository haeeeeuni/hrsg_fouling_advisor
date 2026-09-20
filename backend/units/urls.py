from django.urls import include, path
from rest_framework.routers import DefaultRouter

from units.views import (
    ColumnMappingPreviewView,
    ColumnMappingVersionListView,
    ColumnMappingView,
    StandardFieldListView,
    UnitViewSet,
)

router = DefaultRouter()
router.register("units", UnitViewSet, basename="unit")

urlpatterns = [
    path("standard-fields/", StandardFieldListView.as_view(), name="standard-fields"),
    path(
        "units/<int:unit_id>/column-mappings/",
        ColumnMappingView.as_view(),
        name="unit-column-mappings",
    ),
    path(
        "units/<int:unit_id>/column-mappings/preview/",
        ColumnMappingPreviewView.as_view(),
        name="unit-column-mappings-preview",
    ),
    path(
        "units/<int:unit_id>/column-mappings/versions/",
        ColumnMappingVersionListView.as_view(),
        name="unit-column-mappings-versions",
    ),
    path("", include(router.urls)),
]
