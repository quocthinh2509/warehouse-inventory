# -*- coding: utf-8 -*-
"""
Repository layer for LeaveRequest (thuần DB):
- CRUD, filter, select_for_update, transaction
- Link / unlink Attendance khi cần (theo chỉ thị từ service)
- KHÔNG chứa rule nghiệp vụ (quyền, kiểm tra status hợp lệ...) — service quyết định.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Iterable
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from erp_the20.models import LeaveRequest, Attendance


# ============================
# Base queries
# ============================
def base_qs() -> QuerySet[LeaveRequest]:
    return LeaveRequest.objects.all()

def get_by_id(leave_id: int) -> LeaveRequest:
    return base_qs().get(id=leave_id)

def get_or_none(leave_id: int) -> Optional[LeaveRequest]:
    return base_qs().filter(id=leave_id).first()

def list_my(employee_id: int, statuses: Optional[List[int]] = None) -> QuerySet[LeaveRequest]:
    qs = base_qs().filter(employee_id=employee_id)
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs.order_by("-created_at")

def list_pending_for_manager(date_from: Optional[str] = None, date_to: Optional[str] = None) -> QuerySet[LeaveRequest]:
    qs = base_qs().filter(status=LeaveRequest.Status.SUBMITTED)
    if date_from:
        qs = qs.filter(start_date__gte=date_from)
    if date_to:
        qs = qs.filter(end_date__lte=date_to)
    return qs.order_by("start_date", "employee_id")

def filter_leaves(filters: Dict[str, Any], order_by: Optional[List[str]] = None) -> QuerySet[LeaveRequest]:
    qs = base_qs()
    if (emp_ids := filters.get("employee_id")):
        qs = qs.filter(employee_id__in=emp_ids)
    if (statuses := filters.get("status")):
        qs = qs.filter(status__in=statuses)
    if (leave_types := filters.get("leave_type")):
        qs = qs.filter(leave_type__in=leave_types)
    if (hto := filters.get("handover_to_employee_id")):
        qs = qs.filter(handover_to_employee_id__in=hto)
    if (decided_bys := filters.get("decided_by")):
        qs = qs.filter(decided_by__in=decided_bys)
    if (s_from := filters.get("start_from")):
        qs = qs.filter(start_date__gte=s_from)
    if (s_to := filters.get("start_to")):
        qs = qs.filter(start_date__lte=s_to)
    if (e_from := filters.get("end_from")):
        qs = qs.filter(end_date__gte=e_from)
    if (e_to := filters.get("end_to")):
        qs = qs.filter(end_date__lte=e_to)
    if (qtext := (filters.get("q") or "").strip()):
        qs = qs.filter(reason__icontains=qtext)
    return qs.order_by(*order_by) if order_by else qs.order_by("-created_at")


# ============================
# Mutations (thuần DB)
# ============================
@transaction.atomic
def create(data: Dict[str, Any]) -> LeaveRequest:
    return LeaveRequest.objects.create(**data)

@transaction.atomic
def save_fields(obj: LeaveRequest, patch: Dict[str, Any], allowed: Optional[Iterable[str]] = None) -> LeaveRequest:
    fields: List[str] = []
    for k, v in patch.items():
        if (allowed is None) or (k in allowed):
            setattr(obj, k, v)
            fields.append(k)
    if fields:
        fields.append("updated_at")
        obj.save(update_fields=fields)
    return obj

# ========== Attendance linking helpers (DB-level integrity) ==========
def _unlink_attendances_for_leave(leave: LeaveRequest) -> None:
    Attendance.objects.select_for_update().filter(on_leave=leave).update(on_leave=None)

def _link_leave_to_attendance_on_approve(leave: LeaveRequest) -> None:
    """
    Link leave vào Attendance trong khoảng ngày và huỷ các Attendance đang PENDING/APPROVED.
    (Policy “huỷ khi nghỉ” do service quyết định — repo chỉ thực thi khi được gọi)
    """
    qs = (
        Attendance.objects
        .select_for_update()
        .filter(employee_id=leave.employee_id, date__gte=leave.start_date, date__lte=leave.end_date)
    )
    qs.update(on_leave=leave)
    for att in qs:
        if att.status in (Attendance.Status.PENDING, Attendance.Status.APPROVED):
            att.status = Attendance.Status.CANCELED
            att.is_valid = False
            att.approved_by = None
            att.approved_at = None
            att.save(update_fields=["status", "is_valid", "approved_by", "approved_at", "updated_at"])

@transaction.atomic
def approve_and_link(leave_id: int, manager_id: int, do_link_attendance: bool) -> LeaveRequest:
    """
    Đặt trạng thái APPROVED + decision fields.
    Nếu do_link_attendance=True → thực hiện link leave vào Attendance và auto-cancel chúng.
    """
    obj = LeaveRequest.objects.select_for_update().get(id=leave_id)
    obj.status = LeaveRequest.Status.APPROVED
    obj.decision_ts = timezone.now()
    obj.decided_by = manager_id
    obj.save(update_fields=["status", "decision_ts", "decided_by", "updated_at"])
    if do_link_attendance:
        _link_leave_to_attendance_on_approve(obj)
    return obj

@transaction.atomic
def reject(leave_id: int, manager_id: int) -> LeaveRequest:
    obj = LeaveRequest.objects.select_for_update().get(id=leave_id)
    obj.status = LeaveRequest.Status.REJECTED
    obj.decision_ts = timezone.now()
    obj.decided_by = manager_id
    obj.save(update_fields=["status", "decision_ts", "decided_by", "updated_at"])
    return obj

@transaction.atomic
def cancel(leave_id: int, actor_employee_id: int) -> LeaveRequest:
    obj = LeaveRequest.objects.select_for_update().get(id=leave_id)
    obj.status = LeaveRequest.Status.CANCELLED
    obj.decision_ts = timezone.now()
    obj.decided_by = actor_employee_id
    obj.save(update_fields=["status", "decision_ts", "decided_by", "updated_at"])
    _unlink_attendances_for_leave(obj)
    # Phục hồi các Attendance bị auto-cancel trước đó (nếu policy service yêu cầu có thể gọi thêm hàm khác)
    return obj

@transaction.atomic
def delete_leave(obj: LeaveRequest) -> None:
    _unlink_attendances_for_leave(obj)
    obj.delete()
