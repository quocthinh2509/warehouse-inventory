# attendance_service.py
import math
from dataclasses import dataclass
from datetime import datetime, timedelta  # ✅ cần dùng để build start/end (no grace)

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from erp_the20.models import AttendanceEvent, AttendanceSummary, Worksite, ShiftInstance
from erp_the20.selectors.attendance_selector import get_last_event, get_summary
from erp_the20.selectors.shift_selector import (
    instances_around,
    # instance_window_with_grace,  # ❌ bỏ hẳn (không dùng grace nữa)
    planned_minutes
)

# --------- Geo helpers ---------

def _haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon2) if False else math.radians(lon2 - lon1)  # keep clarity
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi/2)**2) + math.cos(p1)*math.cos(p2)*(math.sin(dlmb/2)**2)
    return 2 * R * math.asin(math.sqrt(a))


def validate_geofence(worksite: Worksite | None, lat, lng, accuracy_m):
    if not worksite or lat is None or lng is None:
        return None, None  # allow, unknown
    try:
        dist = _haversine(lat, lng, worksite.lat, worksite.lng)
    except Exception:
        return None, None
    return worksite, dist


# --------- Shift window WITHOUT grace ---------

def _instance_window(inst: ShiftInstance):
    """
    Trả về (start, end) timezone-aware cho ca theo mẫu, KHÔNG grace.
    Xử lý qua đêm: nếu end <= start và template.overnight => +1 day cho end.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(inst.date, inst.template.start_time), tz)
    end   = timezone.make_aware(datetime.combine(inst.date, inst.template.end_time),   tz)
    if inst.template.overnight and end <= start:
        end += timedelta(days=1)
    return start, end


# --------- Shift matching (no grace) ---------

@dataclass
class MatchConfig:
    checkin_open_grace_min: int
    checkout_grace_min: int
    # Giữ lại nếu sau này bạn muốn bật lại grace; hiện tại không dùng.


def _best_instance_for_ts(ts, *, mode: str, prefer_ids: set[int] | None = None) -> ShiftInstance | None:
    """
    Chọn ShiftInstance hợp lý nhất cho timestamp ts **không dùng grace**:
    - Ứng viên là các instance quanh ngày ts (instances_around(ts))
    - Chỉ nhận instance khi ts nằm trong [start, end] (chuẩn ca)
    - Ưu tiên instance trong prefer_ids (nếu có), sau đó chọn khoảng cách nhỏ nhất đến
      start (mode="in") hoặc đến end (mode="out").
    """
    prefer_ids = prefer_ids or set()
    candidates = []

    for inst in instances_around(ts):
        start, end = _instance_window(inst)
        if not (start <= ts <= end):
            continue  # no grace: ts phải nằm trong khung chuẩn
        if mode == "in":
            score = abs((ts - start).total_seconds())
        else:
            score = abs((end - ts).total_seconds())
        priority = 0 if inst.id in prefer_ids else 1
        candidates.append((priority, score, inst))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


# --------- Public APIs ---------

@transaction.atomic
def add_check_in(
    *, employee, ts=None, lat=None, lng=None, accuracy_m=None,
    source="web", shift_instance_id: int | None = None, worksite_id: int | None = None
):
    """
    Nếu ts không truyền vào => dùng timezone.now() để tự lấy thời điểm server.
    """
    ts = ts or timezone.now()

    inst = None
    if shift_instance_id:
        inst = ShiftInstance.objects.filter(id=shift_instance_id).select_related("worksite", "template").first()
    prefer_ids = {inst.id} if inst else set()

    if not inst:
        inst = _best_instance_for_ts(ts, mode="in", prefer_ids=prefer_ids)

    ws = None
    if worksite_id:
        ws = Worksite.objects.filter(id=worksite_id).first()
    elif inst and inst.worksite:
        ws = inst.worksite
    elif inst and inst.template.default_worksite:
        ws = inst.template.default_worksite

    detected_ws, dist = validate_geofence(ws, lat, lng, accuracy_m)

    ev = AttendanceEvent.objects.create(
        employee=employee,
        shift_instance=inst,
        event_type="check_in",
        ts=ts,
        lat=lat,
        lng=lng,
        accuracy_m=accuracy_m,
        source=source,
        worksite_detected=detected_ws,
        distance_to_worksite_m=dist,
        raw_payload=None,
        is_valid=True,
    )
    _ensure_summary(employee.id, ts.date())
    return ev


@transaction.atomic
def add_check_out(
    *, employee, ts=None, lat=None, lng=None, accuracy_m=None,
    source="web", shift_instance_id: int | None = None, worksite_id: int | None = None
):
    """
    Nếu ts không truyền vào => dùng timezone.now() để tự lấy thời điểm server.
    """
    ts = ts or timezone.now()

    inst = None
    if shift_instance_id:
        inst = ShiftInstance.objects.filter(id=shift_instance_id).select_related("worksite", "template").first()
    prefer_ids = {inst.id} if inst else set()

    if not inst:
        inst = _best_instance_for_ts(ts, mode="out", prefer_ids=prefer_ids)

    ws = None
    if worksite_id:
        ws = Worksite.objects.filter(id=worksite_id).first()
    elif inst and inst.worksite:
        ws = inst.worksite
    elif inst and inst.template.default_worksite:
        ws = inst.template.default_worksite

    detected_ws, dist = validate_geofence(ws, lat, lng, accuracy_m)

    ev = AttendanceEvent.objects.create(
        employee=employee,
        shift_instance=inst,
        event_type="check_out",
        ts=ts,
        lat=lat,
        lng=lng,
        accuracy_m=accuracy_m,
        source=source,
        worksite_detected=detected_ws,
        distance_to_worksite_m=dist,
        raw_payload=None,
        is_valid=True,
    )
    _rollup_summary(employee.id, ts.date(), inst)
    return ev


def _ensure_summary(employee_id: int, date):
    if not get_summary(employee_id, date):
        AttendanceSummary.objects.create(employee_id=employee_id, date=date)


# --- Config nhỏ cho tính toán ---
_MIN_SEGMENT_MIN = 1          # bỏ qua các đoạn làm việc < 1 phút (anti-noise)
_COUNT_OT_MODE = "worked_vs_planned"
# "worked_vs_planned": OT = max(0, worked - planned)
# "after_end_only"   : OT = max(0, last_out - scheduled_end)

def _minutes_between(t1, t2) -> int:
    """Số phút (floor) giữa t1->t2, không âm."""
    if not t1 or not t2:
        return 0
    if t2 <= t1:
        return 0
    return int((t2 - t1).total_seconds() // 60)

def _pair_events_same_day(events: list[AttendanceEvent]) -> tuple[int, list[tuple], object | None, object | None]:
    """
    Ghép cặp check_in/check_out theo thứ tự thời gian trong cùng ngày (đơn giản & an toàn).
    Trả về: (worked_minutes, segments, first_in, last_out)

    segments: list[(in_ts, out_ts)]
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

def _compute_shift_metrics(inst: ShiftInstance | None, *, first_in, last_out, worked_minutes: int) -> tuple[int, int, int]:
    """
    Tính planned / late / early / ot dựa vào ShiftInstance (nếu có), **không dùng grace**.
    - planned: từ template (planned_minutes(inst))
    - late   : max(0, first_in - scheduled_start)
    - early  : max(0, scheduled_end - last_out)
    - OT     : rule theo _COUNT_OT_MODE
    """
    if not inst:
        planned = 0
        late = 0
        early = 0
        ot = max(0, worked_minutes - planned) if _COUNT_OT_MODE == "worked_vs_planned" else 0
        return planned, late, early, ot

    # Lấy giờ chuẩn của ca (no grace)
    start, end = _instance_window(inst)

    planned = planned_minutes(inst)

    # Lateness / Early leave so với giờ chuẩn
    late  = _minutes_between(start, first_in) if first_in and first_in > start else 0
    early = _minutes_between(last_out, end)  if last_out and last_out < end else 0

    if _COUNT_OT_MODE == "worked_vs_planned":
        ot = max(0, worked_minutes - planned)
    else:  # "after_end_only"
        ot = _minutes_between(end, last_out) if last_out and last_out > end else 0

    return planned, late, early, ot

def _rollup_summary(employee_id: int, date, inst: ShiftInstance | None = None):
    """
    Gộp tất cả event trong ngày `date` của employee -> AttendanceSummary:
      - Ghép cặp in/out (bỏ đoạn < _MIN_SEGMENT_MIN)
      - Tính worked/planned/late/early/ot theo giờ chuẩn (no grace)
      - Status: 'present' nếu worked > 0 (trừ khi giữ 'leave'/'holiday')
    Lưu ý: hiện lọc theo ts__date=date. Nếu muốn chuẩn “ca qua đêm” tính cho ngày bắt đầu ca,
    có thể đổi sang filter theo [start, end] của ca (time window) thay vì ts__date.
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

    if worked > 0 and summary.status not in ("leave", "holiday"):
        summary.status = "present"

    summary.save()
