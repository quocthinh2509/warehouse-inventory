# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple, List, Dict

from django.db import transaction
from django.utils import timezone

from erp_the20.models import (
    AttendanceEvent,
    AttendanceSummary,
    LeaveRequest,
    ShiftInstance,
)

GRACE_MINUTES = 5

# Bật/tắt debug print
DEBUG_ATT = True
def _p(msg: str, *args):
    if DEBUG_ATT:
        try:
            print(msg % args)
        except Exception:
            # fallback nếu format sai
            print(msg, *args)

# ====== Time helpers ======
def _resolve_date(d: Optional[date]) -> date:
    out = d or timezone.localdate()
    _p("[_resolve_date] in=%s -> out=%s", d, out)
    return out

def _local_day_bounds(d: date) -> Tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, time.min), tz) +timedelta(hours=6)
    end = start + timedelta(days=1)
    _p("[_local_day_bounds] date=%s tz=%s start=%s end=%s", d, tz, start, end)
    return start, end

# lấy thời gian bắt đầu và kết thúc ca làm, và số giờ nghỉ 
def _shift_window(si: ShiftInstance) -> Tuple[datetime, datetime, int]:
    tz = timezone.get_current_timezone()
    tpl = si.template
    win_start = timezone.make_aware(datetime.combine(si.date, tpl.start_time), tz)
    end_date = si.date + (timedelta(days=1) if tpl.overnight else timedelta(days=0))
    win_end = timezone.make_aware(datetime.combine(end_date, tpl.end_time), tz)
    break_minutes = int(tpl.break_minutes or 0)
    _p("[_shift_window] si_id=%s tpl=%s overnight=%s start=%s end=%s break=%s",
       si.id, tpl.code, tpl.overnight, win_start, win_end, break_minutes)
    return win_start, win_end, break_minutes

# ====== Event helpers ======
def _last_valid_event_before(employee_id: int, ts: datetime) -> Optional[AttendanceEvent]:
    ev = (AttendanceEvent.objects
          .filter(employee_id=employee_id, ts__lt=ts)
          .order_by("-ts")
          .first())
    _p("[_last_valid_event_before] emp=%s ts<%s -> %s",
       employee_id, ts,
       {"id": ev.id, "typ": ev.event_type, "ts": ev.ts} if ev else None)
    return ev

# lấy tất cả attendance event của employee từ thời gian start đến thời gian end 
def _events_in_window(employee_id: int, start: datetime, end: datetime) -> List[AttendanceEvent]:
    qs = (AttendanceEvent.objects
          .filter(employee_id=employee_id, ts__gte=start, ts__lt=end)
          .order_by("ts"))
    events = list(qs)
    first_ts = events[0].ts if events else None
    last_ts = events[-1].ts if events else None
    _p("[_events_in_window] emp=%s window=[%s, %s) count=%d first=%s last=%s",
       employee_id, start, end, len(events), first_ts, last_ts)
    return events

# ====== Stateful calculation (đúng cho ca qua đêm) ======
def _work_minutes_stateful(employee_id: int, win_start: datetime, win_end: datetime) -> Tuple[int, Optional[datetime], Optional[datetime]]:
    """
    Tính worked minutes trong [win_start, win_end) theo state machine.
    Trả thêm (first_in_in_window, last_out_in_window) để dùng cho late/early.
    """
    events = _events_in_window(employee_id, win_start, win_end)
    prev_ev = _last_valid_event_before(employee_id, win_start)

    # Trạng thái tại win_start: đang "IN" nếu sự kiện cuối trước đó là IN.
    clocked_in = (prev_ev is not None and prev_ev.event_type == "in")

    cur = win_start
    worked = 0
    first_in_in_window = None
    last_out_in_window = None

    _p("[_work_minutes_stateful] emp=%s win=[%s, %s) carry_in=%s prev=%s",
       employee_id, win_start, win_end, clocked_in,
       {"id": prev_ev.id, "typ": prev_ev.event_type, "ts": prev_ev.ts} if prev_ev else None)

    for ev in events:
        if clocked_in:
            delta = _minutes_between(cur, ev.ts)
            worked += delta
            _p("   [stateful] add=%s min (cur=%s -> ev=%s)", delta, cur, ev.ts)
        # toggle state
        if ev.event_type == "in":
            clocked_in = True
            cur = ev.ts
            if first_in_in_window is None:
                first_in_in_window = ev.ts
            _p("   [stateful] IN at %s", ev.ts)
        else:  # out
            clocked_in = False
            cur = ev.ts
            last_out_in_window = ev.ts
            _p("   [stateful] OUT at %s", ev.ts)

    # Nếu vẫn đang IN tới cuối ca, cộng phần còn lại đến win_end
    if clocked_in:
        tail = _minutes_between(cur, win_end)
        worked += tail
        _p("   [stateful] tail add=%s min (cur=%s -> win_end=%s)", tail, cur, win_end)

    _p("[_work_minutes_stateful] result worked=%s first_in=%s last_out=%s",
       worked, first_in_in_window, last_out_in_window)
    return worked, first_in_in_window, last_out_in_window

def _minutes_between(a: datetime, b: datetime) -> int:
    secs = (b-a).total_seconds()
    if secs <=0:
        mins=0
    else:
        mins = int((secs+30)//60)
    # mins = max(0, int((b - a).total_seconds() // 60))
    _p("[_minutes_between] a=%s b=%s -> %s", a, b, mins)
    return mins

# ====== Shifts in a day ======
def _list_shift_instances_for_day(employee_id: int, d: date) -> List[ShiftInstance]:
    """
    Mặc định suy luận ca dựa theo shift_instance xuất hiện trong events của NV trong ngày d.
    Nếu bạn có bảng phân công ca theo NV, thay thế logic này cho phù hợp.
    """
    day_start, day_end = _local_day_bounds(d)
    si_ids = (AttendanceEvent.objects
              .filter(employee_id=employee_id, ts__gte=day_start, ts__lt=day_end, shift_instance__isnull=False)
              .values_list("shift_instance_id", flat=True)
              .distinct())
    ids = list(si_ids)
    if not ids:
        _p("[_list_shift_instances_for_day] emp=%s date=%s -> NO shifts inferred", employee_id, d)
        return []
    sis = list(ShiftInstance.objects.select_related("template").filter(id__in=ids).order_by("template_id", "date"))
    _p("[_list_shift_instances_for_day] emp=%s date=%s sis=%s", employee_id, d, [s.id for s in sis])
    return sis

# ====== Leave helpers ======
def _approved_leave_covering_date(employee_id: int, d: date) -> Optional[LeaveRequest]:
    lv = (LeaveRequest.objects
          .filter(employee_id=employee_id, status="approved", start_date__lte=d, end_date__gte=d)
          .order_by("-decision_ts", "-created_at")
          .first())
    _p("[_approved_leave_covering_date] emp=%s date=%s -> %s", employee_id, d, lv.id if lv else None)
    return lv

# ==========================================================
#                    PUBLIC SERVICE API
# ==========================================================
@transaction.atomic
def build_daily_summary(employee_id: int, d: Optional[date] = None) -> AttendanceSummary:
    """
    Build/Upsert AttendanceSummary cho 1 nhân viên trong 1 ngày, hỗ trợ:
    - NHIỀU CA trong ngày
    - CA QUA ĐÊM (start hôm nay, end ngày mai)
    Nguyên tắc: mỗi ca tính độc lập bằng state machine trong [win_start, win_end), rồi cộng dồn.
    """
    try:
        d = _resolve_date(d)
        day_start, day_end = _local_day_bounds(d)

        # Lấy danh sách ca thuộc ngày d (có thể 0, 1, 2-3 ca)
        sis = _list_shift_instances_for_day(employee_id, d)

        planned_total = 0
        worked_total = 0
        late_total = 0
        early_total = 0
        overtime_total = 0

        # Chụp snapshot events cả ngày (để audit UI)
        day_events = _events_in_window(employee_id, day_start, day_end)
        events_snap = [{
            "id": e.id,
            "ts": e.ts.isoformat(),
            "event_type": e.event_type,
            "source": e.source,
            "is_valid": e.is_valid,
            "shift_instance_id": e.shift_instance_id,
        } for e in day_events]

        _p("[build_daily_summary] START emp=%s date=%s has_shifts=%s day_events=%d",
           employee_id, d, bool(sis), len(day_events))

        if sis:
            # Có >=1 ca trong ngày (mỗi ca có thể qua đêm)
            for si in sis:
                win_start, win_end, break_minutes = _shift_window(si)

                # planned theo ca
                planned_i = _minutes_between(win_start, win_end) - break_minutes
                planned_i = max(0, planned_i)

                # worked theo ca (stateful, carry-in)
                worked_i, first_in, last_out = _work_minutes_stateful(employee_id, win_start, win_end)
                
                # ====== ÁP DỤNG ÂN HẠN CHO WORKED ======
                window_mins = _minutes_between(win_start, win_end)
                grace_start = win_start + timedelta(minutes=GRACE_MINUTES)
                grace_end   = win_end   - timedelta(minutes=GRACE_MINUTES)

                pad_start = 0
                if first_in is not None and win_start < first_in <= grace_start:
                # bù phần đầu: coi như làm từ win_start
                    pad_start = _minutes_between(win_start, first_in)

                pad_end = 0
                if last_out is not None and grace_end <= last_out < win_end:
                # bù phần cuối: coi như làm đến win_end
                    pad_end = _minutes_between(last_out, win_end)

                if pad_start or pad_end:
                    worked_i = min(window_mins, worked_i + pad_start + pad_end)
                # ====== HẾT BÙ ÂN HẠN ======

                # trừ break một lần nếu có làm
                if worked_i > 0 and break_minutes > 0:
                    worked_i = max(0, worked_i - break_minutes)

                # late theo ca
                if first_in is None:
                    prev_ev = _last_valid_event_before(employee_id, win_start)
                    late_i = 0 if (prev_ev and prev_ev.event_type == "in") else 0
                else:
                    grace_start = win_start + timedelta(minutes=GRACE_MINUTES)
                    late_i = _minutes_between(grace_start, first_in) if first_in > grace_start else 0

                # early theo ca
                if last_out is None:
                    early_i = 0
                else:
                    grace_end = win_end - timedelta(minutes=GRACE_MINUTES)
                    early_i = _minutes_between(last_out, grace_end) if last_out < grace_end else 0

                overtime_i = max(0, worked_i - planned_i)

                _p("   [shift] si=%s window=[%s,%s) break=%s planned_i=%s worked_i=%s late_i=%s early_i=%s overtime_i=%s",
                   si.id, win_start, win_end, break_minutes, planned_i, worked_i, late_i, early_i, overtime_i)

                planned_total += planned_i
                worked_total += worked_i
                late_total += late_i
                early_total += early_i
                overtime_total += overtime_i

                if worked_i == 0:
                    _p("   [shift] si=%s has ZERO worked within window but events_day=%d",
                       si.id, len(day_events))
        else:
            # Không tìm thấy ca (planned=0) -> tính worked theo cả ngày (stateful trong [00:00, 24:00))
            worked_total, _, _ = _work_minutes_stateful(employee_id, day_start, day_end)
            planned_total = 0
            late_total = 0
            early_total = 0
            overtime_total = worked_total  # xem toàn bộ là ngoài kế hoạch
            _p("[build_daily_summary] NO shifts -> worked_day=%s overtime_day=%s events_day=%d",
               worked_total, overtime_total, len(day_events))

        # Nghỉ phép
        approved_leave = _approved_leave_covering_date(employee_id, d)

        # Status tổng
        if worked_total > 0 or day_events:
            if early_total > 0:
                status = "early_leave"
            elif late_total > 0:
                status = "late"
            else:
                status = "present"
        else:
            status = "absent"  # nếu muốn hiển thị riêng 'on_leave' thì thêm vào choices của model

        _p("[build_daily_summary] DONE emp=%s date=%s planned=%s worked=%s late=%s early=%s overtime=%s status=%s on_leave=%s",
           employee_id, d, planned_total, worked_total, late_total, early_total, overtime_total, status,
           approved_leave.id if approved_leave else None)

        summary, _ = AttendanceSummary.objects.update_or_create(
            employee_id=employee_id,
            date=d,
            defaults=dict(
                planned_minutes=planned_total,
                worked_minutes=worked_total,
                late_minutes=late_total,
                early_leave_minutes=early_total,
                overtime_minutes=overtime_total,
                status=status,
                notes="",
                events=events_snap,
                segments=[],  # có thể build segments riêng nếu cần, nhưng worked đã tính stateful chính xác
                on_leave=approved_leave if approved_leave else None,
            )
        )
        return summary

    except Exception as e:
        _p("[build_daily_summary] FAILED emp=%s date=%s err=%r", employee_id, d, e)
        raise

def rebuild_summaries_for_date(d: Optional[date] = None, employee_ids: Optional[List[int]] = None) -> int:
    try:
        d = _resolve_date(d)
        day_start, day_end = _local_day_bounds(d)

        emp_from_events = (AttendanceEvent.objects
                           .filter(ts__gte=day_start, ts__lt=day_end)
                           .values_list("employee_id", flat=True)
                           .distinct())

        emp_from_leave = (LeaveRequest.objects
                          .filter(status="approved", start_date__lte=d, end_date__gte=d)
                          .values_list("employee_id", flat=True)
                          .distinct())

        target_ids = set(employee_ids or []) or set(emp_from_events) | set(emp_from_leave)
        _p("[rebuild_summaries_for_date] date=%s targets=%d details=%s",
           d, len(target_ids), sorted(target_ids))

        cnt = 0
        for emp_id in target_ids:
            build_daily_summary(emp_id, d)
            cnt += 1

        _p("[rebuild_summaries_for_date] date=%s rebuilt=%s", d, cnt)
        return cnt

    except Exception as e:
        _p("[rebuild_summaries_for_date] FAILED date=%s err=%r", d, e)
        raise
