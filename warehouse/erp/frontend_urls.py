from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='erp/index.html'), name='erp_index'),
    path('hr/', TemplateView.as_view(template_name='erp/hr.html'), name='erp_hr_page'),
    path('attendance/', TemplateView.as_view(template_name='erp/attendance.html'), name='erp_attendance_page'),
    path('leave/', TemplateView.as_view(template_name='erp/leave.html'), name='erp_leave_page'),
    path('payroll/', TemplateView.as_view(template_name='erp/payroll.html'), name='erp_payroll_page'),
]
