from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path(
        "shift-templates/",
        TemplateView.as_view(template_name="erp_the20/shift_templates.html"),
        name="shift-templates-ui",
    ),
    path(
        "attendance_ui/",
        TemplateView.as_view(template_name="erp_the20/attendance_protal.html"),
        name="attendance-templates-ui",
    ),
    path(
        "leave/employee/",
        TemplateView.as_view(template_name="erp_the20/leave_employee.html"),
        name="leave-employee-ui",
        ),
    path(
        "leave/manager/",
        TemplateView.as_view(template_name="erp_the20/leave_manager.html"),
        name="leave-manager-ui",
        ),
    path("ui/notifications/", TemplateView.as_view(template_name="erp_the20/notification_ui.html"), name="notification-ui"),
    path("ui/profile/", TemplateView.as_view(template_name="erp_the20/profile_ui.html"), name="profile-ui"),
    path("ui/proposals/", TemplateView.as_view(template_name="erp_the20/proposal_ui.html"), name="proposal-ui"),
    path("ui/handovers/", TemplateView.as_view(template_name="erp_the20/handover_ui.html"), name="handover-ui"),
]
