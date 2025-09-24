from django.urls import path
from .views.employee_view import EmployeeListCreateView, EmployeeDeactivateView, EmployeeActivateView, EmployeeDetailView, ActiveEmployeeListView
from .views.department_view import  DepartmentListCreateView, DepartmentDetailView, DepartmentActivateView, DepartmentDeactivateView
from .views.worksite_view import WorksiteListCreateView, WorksiteDeactivateView, WorksiteDetailView, WorksiteActivateView, ActiveWorksiteListView
from .views.position_view import PositionListCreateView, PositionDetailView
from .views.shift_view import (
    ShiftTemplateListCreateView, ShiftInstanceListCreateView,
    ShiftRegisterView, ShiftApproveRegistrationView, ShiftDirectAssignView
)
from .views.local_gate_view import LocalVerifyView
from django.views.generic import TemplateView
from .views.attendance_view import CheckInView, CheckOutView, AttendanceSummaryView
from .views.leave_view import LeaveTypeListCreateView, LeaveRequestListCreateView, LeaveApproveView

urlpatterns = [
    # Master
    path("employees/", EmployeeListCreateView.as_view()), 
    path("employees/<int:pk>/", EmployeeDetailView.as_view()),  # Assuming detail view is same as deactivate for now
    path("employees/<int:pk>/activate/", EmployeeActivateView.as_view()),
    path("employees/<int:pk>/deactivate/", EmployeeDeactivateView.as_view()),
    path("employees/active/", ActiveEmployeeListView.as_view()),


    path("departments/", DepartmentListCreateView.as_view()),
    path("departments/<int:pk>/", DepartmentDetailView.as_view()),
    path("departments/<int:pk>/activate/", DepartmentActivateView.as_view()),
    path("departments/<int:pk>/deactivate/", DepartmentDeactivateView.as_view()),

    path("worksites/", WorksiteListCreateView.as_view()),
    path("worksites/<int:pk>/", WorksiteDetailView.as_view()),
    path("worksites/<int:pk>/activate/", WorksiteActivateView.as_view()),
    path("worksites/<int:pk>/deactivate/", WorksiteDeactivateView.as_view()),
    path("worksites/active/", ActiveWorksiteListView.as_view()),

    path("positions/", PositionListCreateView.as_view()),
    path("positions/<int:pk>/", PositionDetailView.as_view()),









    # Shifts
    path("shift-templates/", ShiftTemplateListCreateView.as_view()),
    path("shifts/", ShiftInstanceListCreateView.as_view()),
    path("shifts/<int:shift_id>/register/", ShiftRegisterView.as_view()),
    path("shift-registrations/<int:reg_id>/approve/", ShiftApproveRegistrationView.as_view()),
    path("shifts/<int:shift_id>/assign/", ShiftDirectAssignView.as_view()),

    # Attendance
    path("attend/check-in/", CheckInView.as_view()),
    path("attend/check-out/", CheckOutView.as_view()),
    path("attend/summary/", AttendanceSummaryView.as_view()),
    path("wifi/local/verify/", LocalVerifyView.as_view()),

    # Leave
    path("leave/types/", LeaveTypeListCreateView.as_view()),
    path("leave/requests/", LeaveRequestListCreateView.as_view()),
    path("leave/requests/<int:pk>/approve/", LeaveApproveView.as_view()),
    path("ui/", TemplateView.as_view(template_name="erp_the20/dashboard.html"), name="erp_dashboard"),
    path("ui/shifts/", TemplateView.as_view(template_name="erp_the20/shifts.html"), name="erp_shifts"),
    path("ui/departments/", TemplateView.as_view(template_name="erp_the20/departments.html"), name="erp_departments"),
    path("ui/positions/", TemplateView.as_view(template_name="erp_the20/positions.html"), name="erp_positions"),
    path("ui/locations/", TemplateView.as_view(template_name="erp_the20/locations.html"), name="erp_locations"),
    path("ui/employees/", TemplateView.as_view(template_name="erp_the20/employees.html"), name="erp_employees"),
]
