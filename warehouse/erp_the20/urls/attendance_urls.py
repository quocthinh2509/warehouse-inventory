# erp_the20/urls/attendance_urls.py
from django.urls import path

from django.urls import path
from erp_the20.views.attendance_view import (
    AttendanceCheckInView,
    AttendanceCheckOutView,
    AttendanceEventListView,
    AttendanceSummaryListView,
    AttendanceStatsView,
    ListAttendanceEvent,
    GetLastEvent,
)

urlpatterns = [
    path("check-in/", AttendanceCheckInView.as_view(), name="attendance-check-in"),
    path("check-out/", AttendanceCheckOutView.as_view(), name="attendance-check-out"),
    path("events/", AttendanceEventListView.as_view(), name="attendance-events"),
    path("summaries/", AttendanceSummaryListView.as_view(), name="attendance-summaries"),
    path("stats/", AttendanceStatsView.as_view(), name="attendance-stats"),
    path("list-events/", ListAttendanceEvent.as_view(), name="attendance-stats-employee"),
    path("get-last-event/",GetLastEvent.as_view(), name="get-last-event")

]



