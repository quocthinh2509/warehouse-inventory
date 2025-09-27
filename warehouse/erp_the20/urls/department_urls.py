from django.urls import path
from erp_the20.views.department_view import (
    DepartmentListCreateView,
    DepartmentDetailView,
)

urlpatterns = [
    # /api/departments/
    path("", DepartmentListCreateView.as_view(), name="department-list-create"),
    # /api/departments/<pk>/
    path("<int:pk>/", DepartmentDetailView.as_view(), name="department-detail"),
]
