from django.urls import path
from . import views

urlpatterns = [
    path("attendance/", views.attendance_page, name="attendance_page"),
    path("api/attendance/", views.attendance_api, name="attendance_api"),
    path("api/set-allowed-ip/", views.set_allowed_ip, name="set_allowed_ip"),
]
