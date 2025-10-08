# # erp_the20/urls.py
from rest_framework.routers import DefaultRouter
from erp_the20.views.attendance_view import AttendanceViewSet

router = DefaultRouter()
router.register(r"attendance", AttendanceViewSet, basename="attendance")
urlpatterns = router.urls