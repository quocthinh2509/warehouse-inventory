# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime, timedelta, date as date_type
import logging

from django.db import transaction, IntegrityError, connection
from django.utils import timezone
from django.conf import settings

from erp_the20.models import Attendance, ShiftTemplate, LeaveRequest
from erp_the20.selectors.user_selector import get_external_users_map
from erp_the20.utils.notify import (
    send_lark_notification,
    send_email_notification,
)

logger = logging.getLogger(__name__)

# ========= CORE MINUTES (worked / paid) =========
def _mins(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 60))

def _compute_core_minutes(att: Attendance) -> tuple[int, int]:
    tmpl = att.shift_template
    if not tmpl:
        return 0, 0

    # Khung ca (tự xử lý qua đêm)
    sched_start, sched_end = _window_for(att)
    break_min = int(getattr(tmpl, "break_minutes", 0) or 0)
    sched_minutes = max(0, _mins(sched_start, sched_end) - break_min)

    # Mặc định
    worked = 0
    paid = 0

    # Chỉ tính khi record đã Approved
    if att.status == Attendance.Status.APPROVED:
        # 1) WORKED = giao giữa thời gian làm thực tế & khung ca
        if att.ts_in and att.ts_out and att.ts_out >= att.ts_in:
            overlap_start = max(att.ts_in, sched_start)
            overlap_end = min(att.ts_out, sched_end)
            overlap_min = _mins(overlap_start, overlap_end) if overlap_end > overlap_start else 0
            worked = max(0, overlap_min - break_min)

        # 2) PAID
        leave = getattr(att, "on_leave", None)
        if leave and leave.status == LeaveRequest.Status.APPROVED:
            if bool(leave.paid):
                # nghỉ có lương -> trả đủ phút ca (sau break)
                paid = sched_minutes
            else:
                # nghỉ không lương -> không trả
                paid = 0
        else:
            # không có đơn nghỉ -> trả theo worked
            paid = worked

    return worked, paid

@transaction.atomic
def recalc_and_save_core_minutes(*, attendance_id: int) -> Attendance:
    obj = _for_update(Attendance.objects.select_related("shift_template", "on_leave")).get(id=attendance_id)
    worked, paid = _compute_core_minutes(obj)
    obj.worked_minutes = worked
    obj.paid_minutes = paid
    obj.save(update_fields=["worked_minutes", "paid_minutes", "updated_at"])
    return obj


# ========= helper về DB lock =========
def _supports_for_update() -> bool:
    return getattr(connection.features, "has_select_for_update", False)

def _for_update(qs):
    return qs.select_for_update() if _supports_for_update() else qs

# ========= helper về time window =========
def _aware(dt: datetime) -> datetime:
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())

def _window_for(att: Attendance) -> Tuple[datetime, datetime]:
    tmpl: ShiftTemplate = att.shift_template
    start_naive = datetime.combine(att.date, tmpl.start_time)
    end_naive = datetime.combine(att.date, tmpl.end_time)
    if getattr(tmpl, "overnight", False) or tmpl.end_time <= tmpl.start_time:
        end_naive = end_naive + timedelta(days=1)
    return _aware(start_naive), _aware(end_naive) # trả về 2 datetime aware

def _window_for_params(date_, tmpl: ShiftTemplate) -> Tuple[datetime, datetime]:
    start_naive = datetime.combine(date_, tmpl.start_time)
    end_naive = datetime.combine(date_, tmpl.end_time)
    if getattr(tmpl, "overnight", False) or tmpl.end_time <= tmpl.start_time:
        end_naive = end_naive + timedelta(days=1)
    return _aware(start_naive), _aware(end_naive)

def _overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return not (a_end <= b_start or b_end <= a_start)

# ========= kiểm tra trùng ca (pending/approved) =========
_ACTIVE = {Attendance.Status.PENDING, Attendance.Status.APPROVED}

def _find_conflicts(employee_id: int, date_, tmpl: ShiftTemplate, exclude_id: Optional[int] = None) -> List[Attendance]:
    target_start, target_end = _window_for_params(date_, tmpl)
    candidates = (
        Attendance.objects
        .filter(
            deleted_at__isnull=True,
            employee_id=employee_id,
            status__in=_ACTIVE,
            date__gte=date_ - timedelta(days=1),
            date__lte=date_ + timedelta(days=1),
        )
        .select_related("shift_template")
    )
    if exclude_id:
        candidates = candidates.exclude(id=exclude_id)
    out: List[Attendance] = []
    for s in candidates:
        s_start, s_end = _window_for(s)
        if _overlap(target_start, target_end, s_start, s_end):
            out.append(s)
    return out

def _raise_if_conflict(employee_id: int, date_, tmpl: ShiftTemplate, exclude_id: Optional[int], when: str) -> None:
    conflicts = _find_conflicts(employee_id, date_, tmpl, exclude_id=exclude_id)
    if conflicts:
        details = []
        for c in conflicts:
            s, e = _window_for(c)
            details.append(f"[#{c.id}] {c.shift_template.code} {s:%Y-%m-%d %H:%M}→{e:%Y-%m-%d %H:%M} (status={c.get_status_display()})")
        raise ValueError(f"Trùng thời gian với bản ghi khác: {'; '.join(details)} (bước {when}).")

# ========= tìm đơn nghỉ đã APPROVED bao phủ ngày =========
def _find_approved_leave_for(employee_id: int, date_) -> Optional[LeaveRequest]:
    return (
        LeaveRequest.objects
        .filter(
            deleted_at__isnull=True,
            employee_id=employee_id,
            status=LeaveRequest.Status.APPROVED,
            start_date__lte=date_,
            end_date__gte=date_,
        )
        .order_by("-decision_ts", "-updated_at", "-id")
        .first()
    )

# ========= contact (email + lark) =========
def _resolve_contacts(employee_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    contacts: Dict[int, Dict[str, Any]] = {}
    if not employee_ids:
        return contacts
    try:
        data = get_external_users_map(employee_ids) or {}
    except Exception as ex:
        logger.warning("[attendance] get_external_users_map failed: %s", ex)
        data = {}
    for emp_id in employee_ids:
        u = data.get(int(emp_id)) or {}
        email = (u.get("email") or "").strip()
        lark_open_id = (u.get("lark_open_id") or u.get("open_id") or "").strip()
        emails = [email] if email else []
        contacts[int(emp_id)] = {"emails": emails, "lark_open_id": lark_open_id}
    return contacts

def _attendance_brief(att: Attendance) -> str:
    t = att.shift_template
    s = getattr(t, "start_time", None)
    e = getattr(t, "end_time", None)
    s_txt = s.strftime("%H:%M") if s else "?"
    e_txt = e.strftime("%H:%M") if e else "?"
    code = getattr(t, "code", "") or ""
    name = getattr(t, "name", "") or ""
    return f"{att.date} • {code} ({name}) {s_txt}-{e_txt}"

def _lark_webhook_url() -> Optional[str]:
    return getattr(settings, "LARK_ATTENDANCE_WEBHOOK_URL", None)

def _format_items_brief(atts: List[Attendance]) -> str:
    return "\n".join(f"- {_attendance_brief(a)}" for a in atts)

# ========= CRUD + quyết định =========
def create_attendance(
    *, employee_id: int, shift_template_id: int, date, ts_in=None, ts_out=None,
    source: int, work_mode: int, bonus=None, requested_by: Optional[int] = None
) -> Attendance:
    tmpl = ShiftTemplate.objects.get(id=shift_template_id)
    _raise_if_conflict(employee_id, date, tmpl, exclude_id=None, when="create")
    link_leave = _find_approved_leave_for(employee_id, date)
    with transaction.atomic():
        obj = Attendance.objects.create(
            employee_id=employee_id,
            shift_template=tmpl,
            date=date,
            ts_in=ts_in,
            ts_out=ts_out,
            source=source,
            work_mode=work_mode,
            bonus=bonus or 0,
            status=Attendance.Status.PENDING,
            is_valid=False,
            requested_by=requested_by or employee_id,
            on_leave=link_leave,
        )
        return obj

def update_attendance(
    *, target_id: int, actor_employee_id: int,
    shift_template_id: Optional[int] = None, date=None, ts_in=None, ts_out=None,
    source: Optional[int] = None, work_mode: Optional[int] = None, bonus=None,
    requested_by: Optional[int] = None, actor_is_manager: bool = False
) -> Attendance:
    with transaction.atomic():
        obj = _for_update(Attendance.objects).get(id=target_id)
        tmpl = obj.shift_template
        new_date = obj.date
        if shift_template_id is not None:
            tmpl = ShiftTemplate.objects.get(id=shift_template_id)
        if date is not None:
            new_date = date
        if shift_template_id is not None or date is not None:
            _raise_if_conflict(obj.employee_id, new_date, tmpl, exclude_id=obj.id, when="update")

        # Nếu non-manager sửa bản ghi đã approved => quay về pending
        if not actor_is_manager and obj.status == Attendance.Status.APPROVED:
            obj.status = Attendance.Status.PENDING
            obj.is_valid = False
            obj.approved_by = None
            obj.approved_at = None
            obj.reject_reason = ""

        if shift_template_id is not None:
            obj.shift_template = tmpl
        if date is not None:
            obj.date = new_date
        if ts_in is not None:
            obj.ts_in = ts_in
        if ts_out is not None:
            obj.ts_out = ts_out
        if source is not None:
            obj.source = source
        if work_mode is not None:
            obj.work_mode = work_mode
        if bonus is not None:
            obj.bonus = bonus
        if requested_by is not None:
            obj.requested_by = requested_by

        # Link lại đơn nghỉ (nếu có)
        obj.on_leave = _find_approved_leave_for(obj.employee_id, obj.date)
        obj.save()

        # Nếu record đang Approved thì sau update cần tính lại minutes
        if obj.status == Attendance.Status.APPROVED and obj.is_valid:
            _ = recalc_and_save_core_minutes(attendance_id=obj.id)

        return obj

def soft_delete_attendance(*, target_id: int) -> None:
    with transaction.atomic():
        obj = _for_update(Attendance.objects).get(id=target_id)
        obj.deleted_at = timezone.now()
        obj.save(update_fields=["deleted_at", "updated_at"])

def restore_attendance(*, target_id: int) -> Attendance:
    with transaction.atomic():
        obj = _for_update(Attendance.objects).get(id=target_id)
        obj.deleted_at = None
        obj.save(update_fields=["deleted_at", "updated_at"])
        return obj

def cancel_by_employee(*, actor_user_id: int, target_id: int, actor_is_manager: bool = False) -> Attendance:
    with transaction.atomic():
        obj = _for_update(Attendance.objects).get(id=target_id)
        if not actor_is_manager and obj.employee_id != actor_user_id:
            raise PermissionError("Bạn không có quyền huỷ bản ghi này.")
        if obj.status == Attendance.Status.APPROVED and not actor_is_manager:
            raise PermissionError("Bản ghi đã duyệt, vui lòng liên hệ quản lý để huỷ.")
        obj.status = Attendance.Status.CANCELED
        obj.is_valid = False
        obj.approved_by = None
        obj.approved_at = None
        obj.save(update_fields=["status", "is_valid", "approved_by", "approved_at", "updated_at"])
        return obj

def approve_attendance(*, manager_user_id: int, target_id: int, override_overlap: bool = False) -> Attendance:
    with transaction.atomic():
        obj = _for_update(Attendance.objects.select_related("shift_template")).get(id=target_id)
        if not override_overlap:
            _raise_if_conflict(obj.employee_id, obj.date, obj.shift_template, exclude_id=obj.id, when="approve")
        obj.approve(manager_user_id)
        obj.save(update_fields=["status", "is_valid", "approved_by", "approved_at", "updated_at"])
        _ = recalc_and_save_core_minutes(attendance_id=obj.id)
        return obj

def reject_attendance(*, manager_user_id: int, target_id: int, reason: str = "") -> Attendance:
    with transaction.atomic():
        obj = _for_update(Attendance.objects).get(id=target_id)
        obj.reject(manager_user_id, reason)
        obj.save(update_fields=["status", "is_valid", "approved_by", "approved_at", "reject_reason", "updated_at"])
        return obj

def manager_cancel_attendance(*, manager_user_id: int, target_id: int, reason: str = "") -> Attendance:
    with transaction.atomic():
        obj = _for_update(Attendance.objects).get(id=target_id)
        obj.status = Attendance.Status.CANCELED
        obj.is_valid = False
        obj.approved_by = None
        obj.approved_at = None
        if reason:
            obj.reject_reason = reason
        obj.save(update_fields=["status", "is_valid", "approved_by", "approved_at", "reject_reason", "updated_at"])
        return obj

# ========= ALL-OR-NOTHING batch register =========
def batch_register_attendance(
    *, employee_id: int,
    items: List[Dict[str, Any]],
    default_source: int,
    default_work_mode: int,
    default_bonus
):
    created: List[Attendance] = []
    errors: List[Dict[str, Any]] = []

    if not items:
        return [], [{"index": None, "error": "No items provided."}]

    tpl_ids = {int(it["shift_template"]) for it in items}
    tpl_map: Dict[int, ShiftTemplate] = {t.id: t for t in ShiftTemplate.objects.filter(id__in=tpl_ids)}
    missing_tpl = [tid for tid in tpl_ids if tid not in tpl_map]
    if missing_tpl:
        for i, it in enumerate(items):
            if int(it["shift_template"]) in missing_tpl:
                errors.append({"index": i, "error": f"ShiftTemplate {it['shift_template']} not found"})
        return [], errors

    payload_windows: List[Dict[str, Any]] = []
    min_date: Optional[date_type] = None
    max_date: Optional[date_type] = None
    for i, it in enumerate(items):
        d = it["date"]
        tpl = tpl_map[int(it["shift_template"])]
        start_dt, end_dt = _window_for_params(d, tpl)
        payload_windows.append({"index": i, "date": d, "template_id": tpl.id, "start": start_dt, "end": end_dt})
        if min_date is None or d < min_date:
            min_date = d
        if max_date is None or d > max_date:
            max_date = d

    sorted_pw = sorted(payload_windows, key=lambda x: (x["start"], x["end"]))
    for a_idx in range(len(sorted_pw)):
        a = sorted_pw[a_idx]
        for b_idx in range(a_idx + 1, len(sorted_pw)):
            b = sorted_pw[b_idx]
            if b["start"] >= a["end"]:
                break
            if _overlap(a["start"], a["end"], b["start"], b["end"]):
                errors.append({"index": a["index"], "error": f"Overlaps with another item in payload (index={b['index']}).", "conflict_with_index": b["index"]})
    if errors:
        return [], errors

    q_from = (min_date or timezone.localdate()) - timedelta(days=1)
    q_to = (max_date or timezone.localdate()) + timedelta(days=1)
    existing_qs = (
        Attendance.objects
        .select_related("shift_template")
        .filter(
            deleted_at__isnull=True,
            employee_id=employee_id,
            status__in=_ACTIVE,
            date__gte=q_from,
            date__lte=q_to,
        )
    )
    existing_windows: List[Dict[str, Any]] = []
    for ex in existing_qs:
        tpl = ex.shift_template
        if not tpl:
            continue
        ex_start, ex_end = _window_for_params(ex.date, tpl)
        existing_windows.append({"id": ex.id, "start": ex_start, "end": ex_end})
    for pw in payload_windows:
        for ex in existing_windows:
            if _overlap(pw["start"], pw["end"], ex["start"], ex["end"]):
                errors.append({"index": pw["index"], "error": f"Overlaps with existing attendance id={ex['id']} in DB.", "conflict_attendance_id": ex["id"]})
    if errors:
        return [], errors

    with transaction.atomic():
        for it in items:
            created.append(
                create_attendance(
                    employee_id=employee_id,
                    shift_template_id=int(it["shift_template"]),
                    date=it["date"],
                    ts_in=it.get("ts_in"),
                    ts_out=it.get("ts_out"),
                    source=default_source,
                    work_mode=default_work_mode,
                    bonus=it.get("bonus") or default_bonus,
                    requested_by=employee_id,
                )
            )

    # Notify (giữ logic cũ)
    try:
        brief = _format_items_brief(created)
        text = f"[Attendance] Nhân viên #{employee_id} vừa đăng ký {len(created)} ca:\n{brief}"
        ok = send_lark_notification(
            text=text,
            webhook_url=_lark_webhook_url(),
            object_type="AttendanceBatchRegister",
            object_id=str(employee_id),
            to_user=employee_id,
        )
        if ok:
            logger.info("[attendance] Lark sent (batch-register) for employee_id=%s, items=%s", employee_id, len(created))
        else:
            logger.warning("[attendance] Lark send FAILED (batch-register) for employee_id=%s", employee_id)
    except Exception as ex:
        logger.exception("[attendance] Lark notify exception (batch-register): %s", ex)

    return created, []

def batch_decide_attendance(
    *, manager_user_id: int,
    items: list
):
    updated: List[Attendance] = []
    errors: List[Dict[str, Any]] = []

    for idx, it in enumerate(items or []):
        try:
            att_id = int(it["id"])
            if bool(it["approve"]):
                obj = approve_attendance(
                    manager_user_id=manager_user_id,
                    target_id=att_id,
                    override_overlap=bool(it.get("override_overlap", False))
                )
            else:
                obj = reject_attendance(
                    manager_user_id=manager_user_id,
                    target_id=att_id,
                    reason=it.get("reason") or ""
                )
            updated.append(obj)
        except Exception as e:
            errors.append({"index": idx, "id": it.get("id"), "error": str(e)})

    # Notify giữ nguyên
    try:
        approved_by_emp: Dict[int, List[Attendance]] = {}
        for a in updated:
            if a.status == Attendance.Status.APPROVED:
                approved_by_emp.setdefault(a.employee_id, []).append(a)

        if approved_by_emp:
            emp_ids = list(approved_by_emp.keys())
            contacts = _resolve_contacts(emp_ids)

            total = sum(len(v) for v in approved_by_emp.values())
            lines = [f"[Attendance] Manager #{manager_user_id} đã DUYỆT {total} ca cho {len(approved_by_emp)} nhân viên:"]
            at_user_ids: List[str] = []
            for emp_id, atts in approved_by_emp.items():
                lines.append(f"- Nhân viên #{emp_id}: {len(atts)} ca")
                open_id = (contacts.get(emp_id) or {}).get("lark_open_id") or ""
                if open_id:
                    at_user_ids.append(open_id)

            ok = send_lark_notification(
                text="\n".join(lines),
                at_user_ids=at_user_ids if at_user_ids else None,
                webhook_url=_lark_webhook_url(),
                object_type="AttendanceBatchDecide",
                object_id=str(manager_user_id),
                to_user=manager_user_id,
            )
            if ok:
                logger.info("[attendance] Lark sent (batch-decide) manager_id=%s, total=%s", manager_user_id, total)
            else:
                logger.warning("[attendance] Lark send FAILED (batch-decide) manager_id=%s", manager_user_id)

            for emp_id, atts in approved_by_emp.items():
                emails = (contacts.get(emp_id) or {}).get("emails") or []
                subject = "Ca làm việc của bạn đã được duyệt"
                brief = _format_items_brief(atts)
                text_body = (
                    f"Xin chào,\n\n"
                    f"Các ca sau đã được quản lý (ID {manager_user_id}) duyệt:\n"
                    f"{brief}\n\n"
                    f"Trân trọng."
                )
                html_body = (
                    "<p>Xin chào,</p>"
                    f"<p>Các ca sau đã được quản lý (ID <b>{manager_user_id}</b>) duyệt:</p>"
                    f"<pre style='background:#f6f8fa;padding:12px;border-radius:8px'>{brief}</pre>"
                    "<p>Trân trọng.</p>"
                )
                ok_mail = send_email_notification(
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                    to_emails=emails,
                    object_type="AttendanceApproved",
                    object_id=str(emp_id),
                    to_user=emp_id,
                )
                logger.info("[attendance] Email %s for employee_id=%s (items=%s)",
                            "SENT" if ok_mail else "FAILED", emp_id, len(atts))
    except Exception as ex:
        logger.exception("[attendance] Notify exception (batch-decide): %s", ex)

    return updated, []
