from django.urls import path
from erp_the20.views.employee_view import (
    EmployeeListCreateView,
    EmployeeDetailView,
    EmployeeDeactivateView,
    EmployeeActivateView,
    ActiveEmployeeListView,
    EmployeeGetByUserNameView,
)

urlpatterns = [
    # /api/employees/
    path("", EmployeeListCreateView.as_view(), name="employee-list-create"),
    # /api/employees/<pk>/
    path("<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    # /api/employees/<pk>/deactivate
    path("<int:pk>/deactivate/", EmployeeDeactivateView.as_view(), name="employee-deactivate"),
    # /api/employees/<pk>/activate
    path("<int:pk>/activate/", EmployeeActivateView.as_view(), name="employee-activate"),
    # /api/employees/active/
    path("active/", ActiveEmployeeListView.as_view(), name="employee-active-list"),
    path("<str:user_name>/", EmployeeGetByUserNameView.as_view(), name="employee-get-by-username")
]
