from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r"api/employees", EmployeeViewSet, basename="employees")
router.register(r"api/worksites", WorksiteViewSet, basename="worksites")
router.register(r"api/shifts/templates", ShiftTemplateViewSet, basename="shift-templates")
router.register(r"api/shifts/plans", ShiftPlanViewSet, basename="shift-plans")
router.register(r"api/attend/logs", AttendanceLogViewSet, basename="attend-logs")
router.register(r"api/leave/types", LeaveTypeViewSet, basename="leave-types")
router.register(r"api/leave/requests", LeaveRequestViewSet, basename="leave-requests")
router.register(r"api/shift/registrations", ShiftRegistrationViewSet, basename="shift-registrations")

urlpatterns = [
    path("", include(router.urls)),
    path("api/attend/check", AttendanceCheckView.as_view(), name="attend-check"),
    path("api/timesheet/generate", TimesheetGenerateView.as_view(), name="timesheet-generate"),
    path("api/payroll/preview", PayrollPreviewView.as_view(), name="payroll-preview"),

    # HTML test
    path("attend/check", check_page, name="check-page"),
    path("leave", leave_page, name="leave-page"),
    path("shift/register", shiftreg_page, name="shiftreg-page"),
    path("timesheet", timesheet_page, name="timesheet-page"),
]
