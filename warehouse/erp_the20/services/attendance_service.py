# attendance_service.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Set

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from erp_the20.models import AttendanceEvent, AttendanceSummary, ShiftInstance
from erp_the20.selectors.attendance_selector import get_summary
from erp_the20.selectors.shift_selector import instances_around, planned_minutes


# ---------- Shift window WITHOUT grace ----------

def _instance_window(inst: ShiftInstance) -> Tuple[datetime, datetime]:
    """
    Trả về start/end timezone-aware cho ca theo template, KHÔNG tính thời gian linh hoạt (grace).
    Xử lý ca qua đêm: nếu end <= start và template.overnight => cộng thêm 1 ngày cho end.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(inst.date, inst.template.start_time), tz)
    end = timezone.make_aware(datetime.combine(inst.date, inst.template.end_time), tz)
    if inst.template.overnight and end <= start:
        end += timedelta(days=1)
    return start, end


# ---------- Shift matching (no grace) ----------

@dataclass
class MatchConfig:
    checkin_open_grace_min: int
    checkout_grace_min: int
    # Giữ lại để bật grace sau này nếu cần


def _best_instance_for_ts(ts: datetime, *, mode: str, prefer_ids: Optional[Set[int]] = None) -> Optional[ShiftInstance]:
    """
    Chọn ShiftInstance hợp lý nhất cho timestamp `ts` (không dùng grace).

    Args:
        ts: thời điểm cần check
        mode: "in" hoặc "out"
        prefer_ids: set các instance id được ưu tiên

    Returns:
        ShiftInstance phù hợp hoặc None nếu không tìm thấy
    """
    prefer_ids = prefer_ids or set()
    candidates = []

    for inst in instances_around(ts):
        start, end = _instance_window(inst)
        if not (start <= ts <= end):
            continue  # timestamp không nằm trong ca
        score = abs((ts - start).total_seconds()) if mode == "in" else abs((end - ts).total_seconds())
        priority = 0 if inst.id in prefer_ids else 1
        candidates.append((priority, score, inst))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


def _get_shift_instance(ts: datetime, shift_instance_id: Optional[int], mode: str) -> Optional[ShiftInstance]:
    """
    Helper để lấy ShiftInstance cho check-in/check-out.
    """
    inst = None
    if shift_instance_id:
        inst = ShiftInstance.objects.filter(id=shift_instance_id).select_related("template").first()
    prefer_ids = {inst.id} if inst else set()
    if not inst:
        inst = _best_instance_for_ts(ts, mode=mode, prefer_ids=prefer_ids)
    return inst


# ---------- Public APIs ----------

@transaction.atomic
def add_check_in(*, employee, valid, source, shift_instance_id: Optional[int] = None) -> AttendanceEvent:
    """
    Thêm event check-in cho employee.

    Args:
        employee: nhân viên
        valid: dữ liệu check-in hợp lệ (bool)
        source: nguồn check-in (web/mobile)
        shift_instance_id: ID ca làm cụ thể (nếu có)

    Returns:
        AttendanceEvent vừa tạo
    """
    ts = timezone.now()
    inst = _get_shift_instance(ts, shift_instance_id, mode="in")

    ev = AttendanceEvent.objects.create(
        employee_id=employee,
        shift_instance=inst,
        event_type="in",
        ts=ts,
        source=source,
        raw_payload=valid,
        is_valid=bool(valid),
    )
    print(ev)

    _ensure_summary(employee.id, ts.date())
    return ev


@transaction.atomic
def add_check_out(*, employee, valid, source, shift_instance_id: Optional[int] = None) -> AttendanceEvent:
    """
    Thêm event check-out cho employee.

    Args:
        employee: nhân viên
        valid: dữ liệu check-out hợp lệ (bool)
        source: nguồn check-out
        shift_instance_id: ID ca làm cụ thể (nếu có)

    Returns:
        AttendanceEvent vừa tạo
    """
    ts = timezone.now()
    inst = _get_shift_instance(ts, shift_instance_id, mode="out")

    ev = AttendanceEvent.objects.create(
        employee_id=employee,
        shift_instance=inst,
        event_type="out",
        ts=ts,
        source=source,
        raw_payload=valid,
        is_valid=bool(valid),
    )

    _rollup_summary(employee, ts.date(), inst)
    return ev


def _ensure_summary(employee_id: int, date: datetime.date):
    """
    Đảm bảo AttendanceSummary tồn tại cho employee và ngày cụ thể.
    """
    if not get_summary(employee_id, date):
        AttendanceSummary.objects.create(employee_id=employee_id, date=date)


# ---------- Attendance calculation ----------

_MIN_SEGMENT_MIN = 1          # bỏ qua các đoạn làm việc < 1 phút (anti-noise)
_COUNT_OT_MODE = "worked_vs_planned"
# "worked_vs_planned": OT = max(0, worked - planned)
# "after_end_only": OT = max(0, last_out - scheduled_end)


def _minutes_between(t1: Optional[datetime], t2: Optional[datetime]) -> int:
    """
    Tính số phút (floor) giữa 2 thời điểm, không âm.
    """
    if not t1 or not t2 or t2 <= t1:
        return 0
    return int((t2 - t1).total_seconds() // 60)


def _pair_events_same_day(events: List[AttendanceEvent]) -> Tuple[int, List[Tuple[datetime, datetime]], Optional[datetime], Optional[datetime]]:
    """
    Ghép check-in/check-out theo thứ tự thời gian trong cùng ngày.
    Trả về:
        - worked_minutes
        - segments: list[(in_ts, out_ts)]
        - first_in
        - last_out
    """
    total = 0
    segments = []
    start = None
    first_in = None
    last_out = None

    for ev in events:
        if ev.event_type == "check_in":
            start = ev.ts
            if first_in is None:
                first_in = ev.ts
        elif ev.event_type == "check_out" and start:
            dur = _minutes_between(start, ev.ts)
            if dur >= _MIN_SEGMENT_MIN:
                total += dur
                segments.append((start, ev.ts))
                last_out = ev.ts
            start = None  # reset

    return total, segments, first_in, last_out


def _compute_shift_metrics(inst: Optional[ShiftInstance], *, first_in: Optional[datetime],
                           last_out: Optional[datetime], worked_minutes: int) -> Tuple[int, int, int, int]:
    """
    Tính toán:
        - planned_minutes
        - late_minutes
        - early_leave_minutes
        - overtime_minutes
    """
    if not inst:
        ot = max(0, worked_minutes) if _COUNT_OT_MODE == "worked_vs_planned" else 0
        return 0, 0, 0, ot

    start, end = _instance_window(inst)
    planned = planned_minutes(inst)
    late = _minutes_between(start, first_in) if first_in and first_in > start else 0
    early = _minutes_between(last_out, end) if last_out and last_out < end else 0

    if _COUNT_OT_MODE == "worked_vs_planned":
        ot = max(0, worked_minutes - planned)
    else:
        ot = _minutes_between(end, last_out) if last_out and last_out > end else 0

    return planned, late, early, ot


def _rollup_summary(employee_id: int, date: datetime.date, inst: Optional[ShiftInstance] = None):
    """
    Gộp tất cả event trong ngày `date` của employee -> AttendanceSummary:
        - Ghép cặp in/out (bỏ đoạn < _MIN_SEGMENT_MIN)
        - Tính worked/planned/late/early/ot
        - Cập nhật status: 'present' nếu worked > 0 (trừ leave/holiday)
    """
    events = list(
        AttendanceEvent.objects
        .filter(employee_id=employee_id, ts__date=date)
        .order_by("ts")
    )

    worked, segments, first_in, last_out = _pair_events_same_day(events)
    planned, late, early, ot = _compute_shift_metrics(inst, first_in=first_in, last_out=last_out, worked_minutes=worked)

    summary = get_summary(employee_id, date)
    if not summary:
        summary = AttendanceSummary.objects.create(employee_id=employee_id, date=date)

    summary.planned_minutes = planned
    summary.worked_minutes = worked
    summary.late_minutes = late
    summary.early_leave_minutes = early
    summary.overtime_minutes = ot
    summary.segments = [
        {"check_in": s[0].isoformat(), "check_out": s[1].isoformat()} for s in segments
    ]

    if worked > 0 and summary.status not in ("leave", "holiday"):
        summary.status = "present"

    summary.save()
