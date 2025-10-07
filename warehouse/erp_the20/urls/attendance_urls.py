# erp_the20/urls/attendance_urls.py
from django.urls import path

from django.urls import path
from erp_the20.views.attendance_view import (
    AttendanceEventListView,
    AttendanceSummaryListView,
    AttendanceStatsView,
    ListAttendanceEvent,
    GetLastEvent,
    TodaySummaryView,
    RebuildSummariesTodayView,
)

urlpatterns = [
    # path("check-in/", AttendanceCheckInView.as_view(), name="attendance-check-in"),
    # path("check-out/", AttendanceCheckOutView.as_view(), name="attendance-check-out"),
    # path("events/", AttendanceEventListView.as_view(), name="attendance-events"),
    path("summaries/", AttendanceSummaryListView.as_view(), name="attendance-summaries"),
    path("stats/", AttendanceStatsView.as_view(), name="attendance-stats"),
    path("list-events/", ListAttendanceEvent.as_view(), name="attendance-stats-employee"),
    path("get-last-event/",GetLastEvent.as_view(), name="get-last-event"),
    path("summary/today/",TodaySummaryView.as_view(),name="attendance-build-summary"),
    path("summary/rebuild-today",RebuildSummariesTodayView.as_view(),name="attendance-rebuild-summary")

]



