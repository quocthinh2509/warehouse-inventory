from erp_the20.models import AttendanceEvent, AttendanceSummary, ShiftInstance, AttendanceSummaryV2
from typing import Optional, Iterable
from datetime import date
from django.db.models import QuerySet
from typing import Tuple
# from erp_the20.selectors.shift_selector import get_shift_instance_by_date_and_employee

from django.db.models import OuterRef, Exists, Min

from django.utils import timezone
from django.db.models import OuterRef, Exists, Subquery, Min, F
from datetime import date, datetime, time, timedelta
from django.db import connections

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


def count_currently_clocked_in() -> int: # cái này giữ nguyên
    """
    Đếm số nhân viên đang trong ca (check-in gần nhất là 'in', chưa có check-out sau đó).
    """
    # Lấy event mới nhất của mỗi nhân viên
    last_event = (
        AttendanceEvent.objects
        .filter(employee_id=OuterRef("employee_id"))
        .order_by("-ts")
    )

    currently_in = (
        AttendanceEvent.objects
        .filter(id=Subquery(last_event.values("id")[:1]))
        .filter(event_type="in")
        .values("employee_id")
        .distinct()
        .count()
    )
    return currently_in


def count_late_and_ontime(today: date = None) -> Tuple[int, int]:
    """
    Đếm số nhân viên đi trễ và đúng giờ trong ngày.
    Trả về (late_count, ontime_count).
    """
    if today is None:
        today = timezone.localdate()

    late_count = 0
    ontime_count = 0

    # Lấy các sự kiện check-in trong ngày có gắn shift_instance
    events = (
        AttendanceEvent.objects
        .select_related("shift_instance", "shift_instance__template")
        .filter(
            event_type="in",
            ts__date=today,
            shift_instance__date=today
        )
        .order_by("ts")
    )

    # Lấy lần checkin đầu tiên của từng nhân viên
    employee_first_checkin = {}
    for ev in events:
        if ev.employee_id not in employee_first_checkin:
            employee_first_checkin[ev.employee_id] = ev

    for ev in employee_first_checkin.values():
        shift = ev.shift_instance
        if not shift or not shift.template:
            continue

    # Nếu shift chưa có start_time thì bỏ qua
        if not shift.template.start_time:
            continue

        shift_start = datetime.combine(today, shift.template.start_time)
        shift_start = timezone.make_aware(shift_start, timezone.get_current_timezone())

        if ev.ts > shift_start:
            late_count += 1
        else:
            ontime_count += 1


    return late_count, ontime_count

def list_attendance_full(
    employee_ids: Optional[Iterable[int]] = None,
    username: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    event_type: Optional[str] = None,
):
    """
    Trả về AttendanceEvent objects (RawQuerySet) nhưng có thêm thông tin từ User, ShiftInstance và ShiftTemplate.
    """
    sql = """
        SELECT
            eta.*,                                -- toàn bộ AttendanceEvent
            u."UserName" AS username,
            u.email AS email,
            si.date AS shift_date,
            si.status AS shift_status,
            st.code AS template_code,
            st.name AS template_name,
            st.start_time AS template_start,
            st.end_time AS template_end,
            st.break_minutes,
            st.overnight
        FROM erp_the20_attendanceevent eta
        JOIN "user" u ON eta.employee_id = u.id
        LEFT JOIN erp_the20_shiftinstance si ON eta.shift_instance_id = si.id
        LEFT JOIN erp_the20_shifttemplate st ON si.template_id = st.id
        WHERE 1=1
    """
    params = []

    if employee_ids:
        placeholders = ",".join(["%s"] * len(employee_ids))
        sql += f" AND eta.employee_id IN ({placeholders})"
        params.extend(employee_ids)

    if username:
        sql += ' AND u."UserName" = %s'
        params.append(username)

    if start:
        sql += " AND eta.ts::date >= %s"
        params.append(start)
    if end:
        sql += " AND eta.ts::date <= %s"
        params.append(end)

    if event_type:
        sql += " AND eta.event_type = %s"
        params.append(event_type)

    sql += " ORDER BY eta.ts DESC"

    return AttendanceEvent.objects.raw(sql, params)


def get_last_attendance_event_by_date(employee_id: int, day: date) -> Optional[AttendanceEvent]:
    """
    Trả về AttendanceEvent cuối cùng (ts lớn nhất) trong NGÀY `day` của employee_id.
    Mặc định lọc is_valid=True và tính ngày theo timezone hiện tại của Django.
    """
    return (
        AttendanceEvent.objects
        .filter(employee_id=employee_id,ts__date = day)
        .order_by("-ts")
        .first()
    )


