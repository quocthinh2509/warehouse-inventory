# checks/urls.py
from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # --- PAGES (test UI) ---
    path("attend/test",    TemplateView.as_view(template_name="checks/checkin.html"), name="attend-test"),
    path("attend/history", TemplateView.as_view(template_name="checks/attend_history.html"), name="attend-history"),


    # --- Attendance ---
    path("api/attend/check", views.AttendanceCreateView.as_view(), name="attend-check"),
    path("api/attend/list", views.AttendanceListView.as_view(), name="attend-list"),
    path("api/attend/export", views.AttendanceExportCSVView.as_view(), name="attend-export"),

    # --- Employees ---
    path("api/employees", views.EmployeeListCreateView.as_view(), name="employee-list-create"),
    path("api/employees/<int:pk>", views.EmployeeDetailView.as_view(), name="employee-detail"),

    # --- Departments ---
    path("api/departments", views.DepartmentListCreateView.as_view(), name="department-list-create"),
    path("api/departments/<int:pk>", views.DepartmentDetailView.as_view(), name="department-detail"),

    # --- Worksites ---
    path("api/worksites", views.WorksiteListCreateView.as_view(), name="worksite-list-create"),
    path("api/worksites/<int:pk>", views.WorksiteDetailView.as_view(), name="worksite-detail"),

    # --- EmployeeWorksites ---
    path("api/empworksites", views.EmployeeWorksiteListCreateView.as_view(), name="empworksite-list-create"),
    path("api/empworksites/<int:pk>", views.EmployeeWorksiteDetailView.as_view(), name="empworksite-detail"),
]
