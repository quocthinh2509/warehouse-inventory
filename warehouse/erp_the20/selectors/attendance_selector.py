from erp_the20.models import AttendanceEvent, AttendanceSummary, ShiftInstance
from typing import Optional, Iterable
from datetime import date
from django.db.models import QuerySet
# from erp_the20.selectors.shift_selector import get_shift_instance_by_date_and_employee

from django.db.models import OuterRef, Exists, Min

from django.utils import timezone
from django.db.models import OuterRef, Exists, Subquery, Min, F
from datetime import date, datetime, time

from erp_the20.selectors.shift_selector import list_today_shift_instances
# =========================
# ATTENDANCE EVENT & SUMMARY
# =========================

def get_last_event(employee_id: int):
    """
    Trả về AttendanceEvent mới nhất của nhân viên theo ts giảm dần.
    """
    return AttendanceEvent.objects.filter(employee_id=employee_id).order_by("-ts").first()


def get_summary(employee_id: int, date: date):
    """
    Trả về AttendanceSummary của nhân viên cho ngày cụ thể.
    """
    return AttendanceSummary.objects.filter(employee_id=employee_id, date=date).first()


def list_summaries(employee_id: int):
    """
    Trả về danh sách AttendanceSummary của nhân viên, sắp xếp theo ngày giảm dần.
    """
    return AttendanceSummary.objects.filter(employee_id=employee_id).order_by("-date")


def list_all_summaries():
    """
    Trả về tất cả AttendanceSummary trên hệ thống, theo ngày giảm dần.
    """
    return AttendanceSummary.objects.all().order_by("-date")


def list_summaries_by_date(date: date):
    """
    Trả về danh sách AttendanceSummary của tất cả nhân viên cho một ngày.
    (Không còn order_by theo tên vì không có model Employee, chỉ sort theo employee_id)
    """
    return AttendanceSummary.objects.filter(date=date).order_by("employee_id")


def get_list_event_by_date(employee_id: int, date: date):
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
    qs = AttendanceEvent.objects.select_related("shift_instance", "shift_instance__template").order_by("-ts")

    if employee_ids:
        qs = qs.filter(employee_id__in=employee_ids)
    if start:
        qs = qs.filter(ts__date__gte=start)
    if end:
        qs = qs.filter(ts__date__lte=end)
    return qs

# =============================
# ĐANG TRONG CA
# =============================
def count_currently_clocked_in() -> int:
    """
    Số nhân viên đã check-in nhưng chưa check-out (tính đến thời điểm hiện tại).
    Dựa trên AttendanceEvent và shift_instance.
    """
    subquery = AttendanceEvent.objects.filter(
        employee_id=OuterRef("employee_id"),
        ts__gt=OuterRef("ts")
    ).values("employee_id")

    currently_clocked_in_count = (
        AttendanceEvent.objects.filter(event_type="in")
        .annotate(has_later_event=Exists(subquery))
        .filter(has_later_event=False)
        .values("employee_id")
        .distinct()
        .count()
    )

    return currently_clocked_in_count


# =============================
# ĐI TRỄ & ĐÚNG GIỜ
# =============================
def count_late_and_ontime(today: date | None = None) -> tuple[int, int]:
    """
    Trả về (số người đi trễ, số người đúng giờ) trong ngày.
    Dựa trực tiếp vào shift_instance gắn với AttendanceEvent.
    """
    if today is None:
        today = timezone.localdate()

    late_count = 0
    ontime_count = 0

    # Lấy tất cả AttendanceEvent "in" có shift_instance trong ngày
    events = AttendanceEvent.objects.select_related("shift_instance__template").filter(
        event_type="in",
        ts__date=today,
        shift_instance__date=today
    )

    # group theo nhân viên
    employee_first_checkin = {}
    for ev in events.order_by("ts"):
        eid = ev.employee_id
        if eid not in employee_first_checkin:
            employee_first_checkin[eid] = ev

    for ev in employee_first_checkin.values():
        shift = ev.shift_instance
        if not shift or not shift.template:
            continue

        shift_start = datetime.combine(today, shift.template.start_time)

        if ev.ts > shift_start:
            late_count += 1
        else:
            ontime_count += 1

    return late_count, ontime_count