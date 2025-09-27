from erp_the20.models import AttendanceEvent, AttendanceSummary
from typing import Optional, Iterable
from datetime import date
from django.db.models import QuerySet


# Lấy sự kiện chấm công mới nhất của nhân viên
def get_last_event(employee_id: int):
    """
    Trả về AttendanceEvent mới nhất của nhân viên theo ts giảm dần.
    """
    return AttendanceEvent.objects.filter(employee_id=employee_id).order_by("-ts").first()

# Lấy bảng tổng hợp công cho nhân viên theo ngày
def get_summary(employee_id: int, date):
    """
    Trả về AttendanceSummary của nhân viên cho ngày cụ thể.
    """
    return AttendanceSummary.objects.filter(employee_id=employee_id, date=date).first()

# Lấy tất cả bảng tổng hợp của nhân viên, theo ngày giảm dần
def list_summaries(employee_id: int):
    """
    Trả về danh sách AttendanceSummary của nhân viên, sắp xếp theo ngày giảm dần.
    """
    return AttendanceSummary.objects.filter(employee_id=employee_id).order_by("-date")

# Lấy toàn bộ bảng tổng hợp công của tất cả nhân viên
def list_all_summaries():
    """
    Trả về tất cả AttendanceSummary trên hệ thống, theo ngày giảm dần.
    """
    return AttendanceSummary.objects.all().order_by("-date")

# Lấy tất cả bảng tổng hợp công cho một ngày cụ thể
def list_summaries_by_date(date):
    """
    Trả về danh sách AttendanceSummary của tất cả nhân viên cho một ngày, sắp xếp theo tên nhân viên.
    """
    return AttendanceSummary.objects.filter(date=date).order_by("employee__full_name")

# Lấy danh sách sự kiện chấm công của nhân viên theo ngày
def get_list_event_by_date(employee_id: int, date):
    """
    Trả về danh sách AttendanceEvent của nhân viên theo ngày cụ thể, sắp xếp theo thời gian tăng dần.
    """
    return AttendanceEvent.objects.filter(employee_id=employee_id, ts__date=date).order_by("ts")


def list_attendance_events(
    employee_ids: Optional[Iterable[int]] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> QuerySet[AttendanceEvent]:
    """
    Trả về danh sách AttendanceEvent đã lọc.
    """
    qs = AttendanceEvent.objects.select_related(
        "employee", "shift_instance", "shift_instance__template"
    ).order_by("-ts")

    if employee_ids:
        qs = qs.filter(employee_id__in=employee_ids)
    if start:
        qs = qs.filter(ts__date__gte=start)
    if end:
        qs = qs.filter(ts__date__lte=end)

    return qs