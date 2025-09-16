# ─────────────────────────────────────────────────────────────
# erp/urls.py
# ─────────────────────────────────────────────────────────────
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp.views.hr import DepartmentViewSet, WorksiteViewSet, ShiftViewSet, EmployeeViewSet, LeaveTypeViewSet, LeaveRequestViewSet
from erp.views.attendance import CheckView, RecentAttendanceView
from erp.views.payroll import PayrollPeriodViewSet, PayrollLineViewSet, PayrollPreviewView

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'worksites', WorksiteViewSet, basename='worksite')
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'leave-types', LeaveTypeViewSet, basename='leave-type')
router.register(r'leave-requests', LeaveRequestViewSet, basename='leave-request')
router.register(r'payroll/periods', PayrollPeriodViewSet, basename='payroll-period')
router.register(r'payroll/lines', PayrollLineViewSet, basename='payroll-line')

urlpatterns = [
    path('', include(router.urls)),
    path('attendance/check', CheckView.as_view()),
    path('attendance/recent', RecentAttendanceView.as_view()),
    path('payroll/preview', PayrollPreviewView.as_view()),
]
