# erp_the20/urls/attendance_urls.py
from django.urls import path
from erp_the20.views.attendance_view import (
    ReceiveLocalTokenView,
    CheckInView,
    CheckOutView,
    AttendanceSummaryView,
    DebugTokenListView,
    AttendanceEventListView,
)

urlpatterns = [
    # Nhận token từ agent trong LAN
    path("token/", ReceiveLocalTokenView.as_view(), name="attendance-token"),

    # Check-in / Check-out
    path("checkin/", CheckInView.as_view(), name="attendance-checkin"),
    path("checkout/", CheckOutView.as_view(), name="attendance-checkout"),

    # Lấy danh sách bảng tổng hợp công
    path("summaries/", AttendanceSummaryView.as_view(), name="attendance-summaries"),
    path("debug/tokens/", DebugTokenListView.as_view(), name="debug_tokens"),
    path("events/", AttendanceEventListView.as_view(), name="attendance-event-list"),

]
