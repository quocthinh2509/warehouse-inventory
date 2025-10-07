from django.urls import path, include
urlpatterns = [
    path("departments/", include("erp_the20.urls.department_urls")),
    path("positions/", include("erp_the20.urls.position_urls")),
    path("shifts/", include("erp_the20.urls.shift_urls")),
    path("attendance/", include("erp_the20.urls.attendance_urls")),
    path("leave/",include("erp_the20.urls.leave_urls")),
    path("attendanceV2/",include("erp_the20.urls.attendanceV2_urls")),
]
