# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal

from django.db.models import Q, QuerySet
from django.utils import timezone

from erp_the20.models import Attendance

# ==== helpers ====
def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        out: List[str] = []
        for x in v:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.extend([t for t in s.split(",") if t != ""])
        return out
    s = str(v).strip()
    if not s:
        return []
    return [t for t in s.split(",") if t != ""]

def _to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1","true","t","yes","y"):
        return True
    if s in ("0","false","f","no","n"):
        return False
    return None

def _to_date(v: Any) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except Exception:
        return None

def _to_datetime(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if timezone.is_aware(v) else timezone.make_aware(v, timezone.get_current_timezone())
    try:
        dt = datetime.fromisoformat(str(v))
        return dt if timezone.is_aware(dt) else timezone.make_aware(dt, timezone.get_current_timezone())
    except Exception:
        pass
    d = _to_date(v)
    if d:
        return timezone.make_aware(datetime(d.year, d.month, d.day, 0, 0, 0), timezone.get_current_timezone())
    return None

def _to_decimal(v: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(v))
    except Exception:
        return None

# ==== quick lists ====
def list_my_pending(employee_id: int) -> QuerySet[Attendance]:
    return (
        Attendance.objects
        .filter(deleted_at__isnull=True, employee_id=employee_id, status=Attendance.Status.PENDING)
        .select_related("shift_template", "on_leave")
        .order_by("date", "shift_template_id")
    )

def list_pending_for_manager(date_from: Optional[str] = None, date_to: Optional[str] = None) -> QuerySet[Attendance]:
    qs = Attendance.objects.filter(deleted_at__isnull=True, status=Attendance.Status.PENDING)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs.select_related("shift_template", "on_leave").order_by("date", "employee_id")

def get_by_id(attendance_id: int) -> Attendance:
    return Attendance.objects.select_related("shift_template", "on_leave").get(id=attendance_id)

def get_or_none(attendance_id: int) -> Optional[Attendance]:
    return Attendance.objects.filter(id=attendance_id).select_related("shift_template", "on_leave").first()

# ==== powerful filter ====
def filter_attendances(filters: Dict[str, Any], include_deleted: bool = False,
                       order_by: Optional[List[str]] = None) -> QuerySet[Attendance]:
    """
    Hỗ trợ:
      - employee_id, status, work_mode, source (IN / equals)
      - khoảng ngày/giờ: date/
      - template_code, template_name_icontains
      - q: tìm trên code/name template & reject_reason
    """
    base = Attendance.objects.select_related("shift_template", "on_leave")
    if not include_deleted:
        base = base.filter(deleted_at__isnull=True)

    # equals / IN
    employee_ids = _as_list(filters.get("employee_id"))
    if employee_ids:
        base = base.filter(employee_id__in=[int(x) for x in employee_ids if str(x).isdigit()])

    statuses = _as_list(filters.get("status"))
    if statuses:
        ints: List[int] = []
        for s in statuses:
            if str(s).isdigit():
                ints.append(int(s))
            else:
                mapping = {lbl: val for val, lbl in Attendance.Status.choices}
                rev = {lbl.lower(): val for val, lbl in mapping.items()}
                if s.lower() in rev:
                    ints.append(rev[s.lower()])
        if ints:
            base = base.filter(status__in=ints)

    work_modes = _as_list(filters.get("work_mode"))
    if work_modes:
        ints = [int(x) for x in work_modes if str(x).isdigit()]
        base = base.filter(work_mode__in=ints)

    sources = _as_list(filters.get("source"))
    if sources:
        ints = [int(x) for x in sources if str(x).isdigit()]
        base = base.filter(source__in=ints)

    template_codes = _as_list(filters.get("template_code"))
    if template_codes:
        base = base.filter(shift_template__code__in=template_codes)

    approved_bys = _as_list(filters.get("approved_by"))
    if approved_bys:
        base = base.filter(approved_by__in=[int(x) for x in approved_bys if str(x).isdigit()])

    requested_bys = _as_list(filters.get("requested_by"))
    if requested_bys:
        base = base.filter(requested_by__in=[int(x) for x in requested_bys if str(x).isdigit()])

    # booleans
    is_valid = _to_bool(filters.get("is_valid"))
    if is_valid is not None:
        base = base.filter(is_valid=is_valid)

    # dates
    d_from = _to_date(filters.get("date_from") or filters.get("shift_date_from"))
    if d_from:
        base = base.filter(date__gte=d_from)
    d_to = _to_date(filters.get("date_to") or filters.get("shift_date_to"))
    if d_to:
        base = base.filter(date__lte=d_to)

    # text search
    name_icontains = filters.get("template_name_icontains") or filters.get("template_name")
    if name_icontains:
        base = base.filter(shift_template__name__icontains=str(name_icontains).strip())

    q_text = (filters.get("q") or "").strip()
    if q_text:
        base = base.filter(
            Q(shift_template__name__icontains=q_text) |
            Q(shift_template__code__icontains=q_text) |
            Q(reject_reason__icontains=q_text)
        )

    # order
    if order_by:
        base = base.order_by(*order_by)
    else:
        base = base.order_by("-date", "employee_id")
    return base


# ==== Radio options: ca hiện tại & ca sắp tới ====
def _sched_window(att: Attendance) -> Tuple[Optional[datetime], Optional[datetime]]:
    t = att.shift_template
    if not t or not att.date:
        return None, None
    tz = timezone.get_current_timezone()
    start_naive = datetime.combine(att.date, t.start_time)
    end_naive = datetime.combine(att.date, t.end_time)
    if getattr(t, "overnight", False) or t.end_time <= t.start_time:
        end_naive += timedelta(days=1)
    start_dt = timezone.make_aware(start_naive, tz) if not timezone.is_aware(start_naive) else start_naive
    end_dt = timezone.make_aware(end_naive,   tz) if not timezone.is_aware(end_naive)   else end_naive
    return start_dt, end_dt

def list_shift_options(
    *, employee_id: int,
    at_ts: Optional[datetime] = None,
    horizon_minutes: int = 360,
) -> List[Dict[str, Any]]:
    """
    Trả về danh sách các ca quanh thời điểm `at_ts` để FE hiển thị radio:
      - include các ca có khung [sched_start, sched_end] giao với [at_ts - 2h, at_ts + horizon]
      - gắn cờ is_current nếu at_ts ∈ [sched_start, sched_end]
      - sort: is_current desc, start asc
    """
    now = at_ts or timezone.now()
    if not timezone.is_aware(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())

    # truy vấn các bản ghi trong khoảng ngày [-1, +1] để cover ca qua đêm
    q_from = timezone.localdate(now) - timedelta(days=1)
    q_to   = timezone.localdate(now) + timedelta(days=1)

    qs = (
        Attendance.objects
        .filter(
            deleted_at__isnull=True,
            employee_id=employee_id,
            status__in=[Attendance.Status.PENDING, Attendance.Status.APPROVED],
            date__gte=q_from,
            date__lte=q_to,
        )
        .select_related("shift_template", "on_leave")
    )

    window_start = now - timedelta(hours=2)
    window_end = now + timedelta(minutes=max(0, horizon_minutes))

    opts: List[Dict[str, Any]] = []
    for att in qs:
        s, e = _sched_window(att)
        if not s or not e:
            continue
        if e <= window_start or s >= window_end:
            continue

        is_current = (s <= now <= e)
        starts_in = int((s - now).total_seconds() // 60)
        ends_in   = int((e - now).total_seconds() // 60)
        opts.append({
            "id": att.id,
            "employee_id": att.employee_id,
            "shift_template": att.shift_template_id,
            "template_code": getattr(att.shift_template, "code", None),
            "template_name": getattr(att.shift_template, "name", None),
            "date": att.date,
            "sched_start": s,
            "sched_end": e,
            "is_current": is_current,
            "starts_in_minutes": starts_in,
            "ends_in_minutes": ends_in,
            "status": att.status,
            "status_display": att.get_status_display(),
        })

    opts.sort(key=lambda x: (not x["is_current"], x["sched_start"]))
    return opts
