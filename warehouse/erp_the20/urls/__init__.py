# erp_the20/urls/__init__.py
from django.urls import path, include

urlpatterns = [
    # Giao diện (namespaced)
    path("", include(("erp_the20.urls.frontend_urls", "erp_the20"), namespace="erp_the20")),

    # Các nhóm API/route khác (không namespaced, trừ khi bạn muốn)
    path("departments/", include("erp_the20.urls.department_urls")),
    path("positions/", include("erp_the20.urls.position_urls")),
    path("shifts/", include("erp_the20.urls.shift_urls")),
    path("attendance/", include("erp_the20.urls.attendance_urls")), 
    path("leave/", include("erp_the20.urls.leave_urls")),
    # path("attendanceV2/", include("erp_the20.urls.attendanceV2_urls")),
]
