from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp_the20.views.attendance_view import AttendanceViewSet

router = DefaultRouter()
router.register(r"", AttendanceViewSet, basename="attendance")  # <-- root, KHÔNG 'attendance'

urlpatterns = [
    path("", include(router.urls)),
]
