from django.urls import path, include
from erp_the20.views.debug_cache import DebugTokensView
urlpatterns = [
    path("debug/tokens/", DebugTokensView.as_view(), name="debug-tokens"),
    path("departments/", include("erp_the20.urls.department_urls")),
    path("positions/", include("erp_the20.urls.position_urls")),
    path("shifts/", include("erp_the20.urls.shift_urls")),
    path("attendance/", include("erp_the20.urls.attendance_urls")),
]
