from django.urls import include, path
from rest_framework.routers import DefaultRouter

from units.views import (
    ColumnMappingPreviewView,
    ColumnMappingVersionListView,
    ColumnMappingView,
    StandardFieldListView,
    UnitViewSet,
)
from units.views_settings import (
    EffectiveSettingsView,
    SettingListView,
    SettingRestoreDefaultsView,
    UnitSettingDeleteView,
    UnitSettingView,
)

router = DefaultRouter()
router.register("units", UnitViewSet, basename="unit")

urlpatterns = [
    path("standard-fields/", StandardFieldListView.as_view(), name="standard-fields"),
    # --- 설정값 (specs/15 §10) ---
    path("settings/", SettingListView.as_view(), name="settings"),
    path(
        "settings/restore-defaults/",
        SettingRestoreDefaultsView.as_view(),
        name="settings-restore-defaults",
    ),
    path("settings/effective/", EffectiveSettingsView.as_view(), name="settings-effective"),
    path("units/<int:unit_id>/settings/", UnitSettingView.as_view(), name="unit-settings"),
    path(
        "units/<int:unit_id>/settings/<str:key>/",
        UnitSettingDeleteView.as_view(),
        name="unit-setting-delete",
    ),
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
