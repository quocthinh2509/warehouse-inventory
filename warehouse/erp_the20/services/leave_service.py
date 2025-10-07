# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Any, List

from django.db import transaction, router
from django.utils import timezone
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
import logging
import json
import urllib.request
import urllib.error

from erp_the20.models import LeaveRequest, AttendanceSummaryV2

# ====== lấy email & tên người dùng từ user_selector ======
try:
    from erp_the20.selectors.user_selector import get_employee_email, get_employee_fullname
except Exception:
    def get_employee_email(_): return None
    def get_employee_fullname(_): return None

logger = logging.getLogger(__name__)

# ===================== LARK HELPERS =====================

def _lark_webhook_url() -> Optional[str]:
    return getattr(settings, "LARK_LEAVE_WEBHOOK_URL", None)

def _lark_post(payload: dict) -> None:
    """
    Gửi JSON tới Lark Incoming Webhook. Không raise lỗi để không chặn flow nghiệp vụ.
    """
    url = _lark_webhook_url()
    if not url:
        return
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=getattr(settings, "LARK_TIMEOUT", 8)) as resp:
            _ = resp.read()  # không dùng nhưng đọc để flush
        logger.info("[leave_service] Lark sent: %s", payload.get("msg_type"))
    except urllib.error.HTTPError as e:
        logger.warning("[leave_service] Lark HTTPError %s: %s", e.code, e.read())
    except Exception as e:
        logger.warning("[leave_service] Lark post failed: %s", e)

def _lark_text(text: str) -> None:
    """
    Gửi tin nhắn text đơn giản.
    """
    _lark_post({
        "msg_type": "text",
        "content": {"text": text},
    })

def _maybe_at_user(open_id: Optional[str], label: str) -> str:
    """
    Trả về chuỗi @mention nếu có open_id; ngược lại trả về label thường.
    """
    if open_id:
        return f'<at user_id="{open_id}">{label}</at>'
    return label

def _notify_lark_new_leave(leave: LeaveRequest, manager_id: int) -> None:
    url = _lark_webhook_url()
    if not url:
        return

    emp_name = get_employee_fullname(leave.employee_id) or f"Emp#{leave.employee_id}"
    # Nếu có map open_id → @ quản lý
    at_mgr_open_id = (getattr(settings, "LARK_AT_MANAGER_IDS", {}) or {}).get(int(manager_id))
    at_mgr = _maybe_at_user(at_mgr_open_id, f"Manager#{manager_id}")

    text = (
        f"[Leave] New request\n"
        f"- Employee: {emp_name} (ID {leave.employee_id})\n"
        f"- Paid: {'Yes' if leave.paid else 'No'}\n"
        f"- Period: {leave.start_date} → {leave.end_date}\n"
        f"- Hours: {leave.hours or '-'}\n"
        f"- Reason: {leave.reason or '-'}\n"
        f"- Status: {leave.status}\n"
        f"Ping: {at_mgr}"
    )
    _lark_text(text)

def _notify_lark_decision(leave: LeaveRequest, manager_id: int) -> None:
    url = _lark_webhook_url()
    if not url:
        return

    emp_name = get_employee_fullname(leave.employee_id) or f"Emp#{leave.employee_id}"
    # Nếu có map open_id → @ nhân viên
    at_emp_open_id = (getattr(settings, "LARK_AT_EMPLOYEE_IDS", {}) or {}).get(int(leave.employee_id))
    at_emp = _maybe_at_user(at_emp_open_id, emp_name)

    status = leave.status.upper()
    text = (
        f"[Leave] {status}\n"
        f"- Employee: {at_emp} (ID {leave.employee_id})\n"
        f"- Paid: {'Yes' if leave.paid else 'No'}\n"
        f"- Period: {leave.start_date} → {leave.end_date}\n"
        f"- Hours: {leave.hours or '-'}\n"
        f"- Decided by: Manager#{manager_id}\n"
    )
    _lark_text(text)



# ===================== DB & Transaction helpers =====================

def _db_alias() -> str:
    return router.db_for_write(LeaveRequest)

def _atomic():
    return transaction.atomic(using=_db_alias())

# ===================== Email helpers =====================

def _send_email(subject: str, text_body: str, to_emails: List[str], html_body: Optional[str] = None) -> None:
    to_list = [e for e in (to_emails or []) if e]
    if not to_list:
        logger.info("[leave_service] Skip email: empty recipients for %s", subject)
        return
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@example.com"
    try:
        msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=to_list)
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=True)
        logger.info("[leave_service] Sent email to %s: %s", to_list, subject)
    except Exception as ex:
        logger.warning("[leave_service] Email failed to %s: %s", to_list, ex)

def _notify_manager_new_leave(leave: LeaveRequest, manager_id: int) -> None:
    mgr_mail = get_employee_email(manager_id)
    if not mgr_mail:
        logger.info("[leave_service] Skip notify manager: email not found for manager_id=%s", manager_id)
        return
    emp_name = get_employee_fullname(leave.employee_id) or f"Emp#{leave.employee_id}"
    subject = f"[Leave] New request from {emp_name} ({leave.start_date} → {leave.end_date})"
    text = (
        f"Hello,\n\n"
        f"There is a new leave request waiting for your approval:\n"
        f"- Employee: {emp_name} (ID {leave.employee_id})\n"
        f"- Paid: {'Yes' if leave.paid else 'No'}\n"
        f"- Period: {leave.start_date} → {leave.end_date}\n"
        f"- Hours: {leave.hours or '-'}\n"
        f"- Reason: {leave.reason or '-'}\n"
        f"- Status: {leave.status}\n"
    )
    html = (
        f"<p>Hello,</p>"
        f"<p>New leave request waiting for your approval:</p>"
        f"<ul>"
        f"<li><b>Employee:</b> {emp_name} (ID {leave.employee_id})</li>"
        f"<li><b>Paid:</b> {'Yes' if leave.paid else 'No'}</li>"
        f"<li><b>Period:</b> {leave.start_date} → {leave.end_date}</li>"
        f"<li><b>Hours:</b> {leave.hours or '-'}</li>"
        f"<li><b>Reason:</b> {leave.reason or '-'}</li>"
        f"<li><b>Status:</b> {leave.status}</li>"
        f"</ul>"
    )
    _send_email(subject, text, [mgr_mail], html)

def _notify_employee_decision(leave: LeaveRequest, manager_id: int) -> None:
    emp_mail = get_employee_email(leave.employee_id)
    if not emp_mail:
        logger.info("[leave_service] Skip notify employee: email not found for emp_id=%s", leave.employee_id)
        return
    emp_name = get_employee_fullname(leave.employee_id) or f"Emp#{leave.employee_id}"

    if leave.status == "approved":
        subject = f"[Leave] Approved: {leave.start_date} → {leave.end_date}"
        text = (
            f"Hello {emp_name},\n\n"
            f"Your leave request has been APPROVED.\n"
            f"- Paid: {'Yes' if leave.paid else 'No'}\n"
            f"- Period: {leave.start_date} → {leave.end_date}\n"
            f"- Hours: {leave.hours or '-'}\n"
            f"- Decided by: Manager#{manager_id}\n"
        )
        html = (
            f"<p>Hello {emp_name},</p>"
            f"<p>Your leave request has been <b>APPROVED</b>.</p>"
            f"<ul>"
            f"<li><b>Paid:</b> {'Yes' if leave.paid else 'No'}</li>"
            f"<li><b>Period:</b> {leave.start_date} → {leave.end_date}</li>"
            f"<li><b>Hours:</b> {leave.hours or '-'}</li>"
            f"<li><b>Decided by:</b> Manager#{manager_id}</li>"
            f"</ul>"
        )
    elif leave.status == "rejected":
        subject = f"[Leave] Rejected: {leave.start_date} → {leave.end_date}"
        text = (
            f"Hello {emp_name},\n\n"
            f"Your leave request has been REJECTED.\n"
            f"- Period: {leave.start_date} → {leave.end_date}\n"
            f"- Hours: {leave.hours or '-'}\n"
            f"- Decided by: Manager#{manager_id}\n"
            f"If you need more details, please contact your manager."
        )
        html = (
            f"<p>Hello {emp_name},</p>"
            f"<p>Your leave request has been <b>REJECTED</b>.</p>"
            f"<ul>"
            f"<li><b>Period:</b> {leave.start_date} → {leave.end_date}</li>"
            f"<li><b>Hours:</b> {leave.hours or '-'}</li>"
            f"<li><b>Decided by:</b> Manager#{manager_id}</li>"
            f"</ul>"
            f"<p>If you need more details, please contact your manager.</p>"
        )
    elif leave.status == "cancelled":
        subject = f"[Leave] Cancelled: {leave.start_date} → {leave.end_date}"
        text = (
            f"Hello {emp_name},\n\n"
            f"Your leave request has been CANCELLED.\n"
            f"- Period: {leave.start_date} → {leave.end_date}\n"
        )
        html = (
            f"<p>Hello {emp_name},</p>"
            f"<p>Your leave request has been <b>CANCELLED</b>.</p>"
            f"<ul><li><b>Period:</b> {leave.start_date} → {leave.end_date}</li></ul>"
        )
    else:
        return

    _send_email(subject, text, [emp_mail], html)

# ===================== Domain helpers =====================

def _ensure_editable(obj: LeaveRequest, actor_employee_id: int, as_manager: bool = False) -> None:
    if as_manager:
        return
    if obj.employee_id != actor_employee_id:
        raise PermissionError("Không có quyền thao tác trên đơn này.")
    if obj.status != "submitted" or obj.decision_ts is not None:
        raise ValueError("Chỉ thao tác khi đơn đang ở trạng thái submitted (chưa có quyết định).")

def _link_leave_to_summaries(leave: LeaveRequest, db_alias: str) -> None:
    qs = (
        AttendanceSummaryV2.objects.using(db_alias)
        .filter(
            employee_id=leave.employee_id,
            shift_instance__date__gte=leave.start_date,
            shift_instance__date__lte=leave.end_date,
        )
        .select_for_update()
    )
    qs.update(on_leave=leave)
    if leave.hours is None:
        to_cancel = qs.filter(
            status__in=[AttendanceSummaryV2.Status.PENDING, AttendanceSummaryV2.Status.APPROVED]
        )
        for s in to_cancel:
            s.status = AttendanceSummaryV2.Status.CANCELED
            s.is_valid = False
            s.approved_by = None
            s.approved_at = None
            s.save(
                using=db_alias,
                update_fields=["status", "is_valid", "approved_by", "approved_at", "updated_at"],
            )

# ===================== Employee APIs =====================

def create_leave(
    employee_id: int,
    start_date,
    end_date,
    *,
    manager_id: int,                 # <-- bắt buộc truyền để gửi mail cho quản lý
    paid: bool = False,
    hours: Optional[float] = None,
    reason: str = "",
) -> LeaveRequest:
    """
    Tạo đơn nghỉ — mặc định 'submitted'.
    Sau khi tạo, gửi mail thông báo cho quản lý (theo manager_id).
    """
    if end_date < start_date:
        raise ValueError("end_date phải >= start_date.")

    db_alias = _db_alias()
    with _atomic():
        obj = LeaveRequest.objects.using(db_alias).create(
            employee_id=employee_id,
            paid=paid,
            start_date=start_date,
            end_date=end_date,
            hours=hours,
            reason=reason or "",
            status="submitted",
            decision_ts=None,
            decided_by=None,
        )

    # gửi email cho quản lý ngoài transaction
    try:
        _notify_manager_new_leave(obj, manager_id=manager_id)
    except Exception as ex:
        logger.warning("[leave_service] notify manager failed: %s", ex)

    try:
        _notify_manager_new_leave(obj, manager_id=manager_id)   # email (đã có)
    except Exception as ex:
        logger.warning("[leave_service] notify manager email failed: %s", ex)

    # NEW: gửi Lark
    try:
        _notify_lark_new_leave(obj, manager_id=manager_id)
    except Exception as ex:
        logger.warning("[leave_service] notify Lark new leave failed: %s", ex)

    return obj


def update_leave(
    leave_id: int,
    employee_id: int,
    **changes: Any,
) -> LeaveRequest:
    for k in ("employee_id", "status", "decision_ts", "decided_by", "id", "pk", "created_at", "updated_at"):
        changes.pop(k, None)

    db_alias = _db_alias()
    with _atomic():
        obj = (
            LeaveRequest.objects.using(db_alias)
            .select_for_update()
            .get(id=leave_id)
        )
        _ensure_editable(obj, actor_employee_id=employee_id, as_manager=False)

        for field in ("paid", "start_date", "end_date", "hours", "reason"):
            if field in changes and changes[field] is not None:
                setattr(obj, field, changes[field])

        if obj.end_date < obj.start_date:
            raise ValueError("end_date phải >= start_date.")

        obj.save(using=db_alias)
        return obj


def delete_leave(leave_id: int, employee_id: int) -> None:
    db_alias = _db_alias()
    with _atomic():
        obj = (
            LeaveRequest.objects.using(db_alias)
            .select_for_update()
            .get(id=leave_id)
        )
        _ensure_editable(obj, actor_employee_id=employee_id, as_manager=False)
        obj.delete(using=db_alias)


def cancel_leave(leave_id: int, actor_employee_id: int, as_manager: bool = False) -> LeaveRequest:
    db_alias = _db_alias()
    with _atomic():
        obj = (
            LeaveRequest.objects.using(db_alias)
            .select_for_update()
            .get(id=leave_id)
        )

        if not as_manager:
            _ensure_editable(obj, actor_employee_id=actor_employee_id, as_manager=False)

        if obj.status == "cancelled":
            return obj

        obj.status = "cancelled"
        obj.decision_ts = timezone.now()
        obj.decided_by = actor_employee_id
        obj.save(using=db_alias, update_fields=["status", "decision_ts", "decided_by", "updated_at"])

    # Thông báo nhân viên (tuỳ policy; ở đây vẫn gửi)
    try:
        _notify_employee_decision(obj, manager_id=actor_employee_id)
    except Exception as ex:
        logger.warning("[leave_service] notify employee cancel failed: %s", ex)

    try:
        _notify_lark_decision(obj, manager_id=actor_employee_id)
    except Exception as ex:
        logger.warning("[leave_service] notify Lark cancel failed: %s", ex)

    return obj

# ===================== Manager decision =====================

def manager_decide(
    leave_id: int,
    manager_id: int,
    approve: bool,
) -> LeaveRequest:
    """
    Quản lý duyệt/từ chối đơn:
      - Chỉ xử lý đơn ở 'submitted'.
      - Approve: link tới AttendanceSummaryV2 & (nếu nghỉ theo ngày) huỷ ca pending/approved.
      - Ghi decided_by/decision_ts và gửi mail cho nhân viên.
    """
    db_alias = _db_alias()
    with _atomic():
        obj = (
            LeaveRequest.objects.using(db_alias)
            .select_for_update()
            .get(id=leave_id)
        )

        if obj.status != "submitted":
            raise ValueError("Chỉ quyết định đơn ở trạng thái submitted.")

        obj.decision_ts = timezone.now()
        obj.decided_by = manager_id

        if approve:
            obj.status = "approved"
            obj.save(using=db_alias, update_fields=["status", "decision_ts", "decided_by", "updated_at"])
            _link_leave_to_summaries(obj, db_alias=db_alias)
        else:
            obj.status = "rejected"
            obj.save(using=db_alias, update_fields=["status", "decision_ts", "decided_by", "updated_at"])

    # gửi mail cho nhân viên ngoài transaction
    try:
        _notify_employee_decision(obj, manager_id=manager_id)
    except Exception as ex:
        logger.warning("[leave_service] notify employee decision failed: %s", ex)

    try:
        _notify_employee_decision(obj, manager_id=manager_id)   # email (đã có)
    except Exception as ex:
        logger.warning("[leave_service] notify employee email failed: %s", ex)

    # NEW: gửi Lark
    try:
        _notify_lark_decision(obj, manager_id=manager_id)
    except Exception as ex:
        logger.warning("[leave_service] notify Lark decision failed: %s", ex)

    return obj
