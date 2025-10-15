# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict, Any
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from erp_the20.models import Handover, HandoverItem

# Mọi thao tác DB dùng alias này
ERP_DB_ALIAS = "erp_postgres"

# ========================= Helpers =========================
def _maybe_for_update(qs: QuerySet) -> QuerySet:
    """
    Chỉ thêm SELECT ... FOR UPDATE nếu connection(alias) đang ở trong atomic block.
    """
    try:
        conn = transaction.get_connection(using=ERP_DB_ALIAS)
        if getattr(conn, "in_atomic_block", False):
            return qs.select_for_update()
    except Exception:
        pass
    return qs

# ========================= Queries (đọc) =========================
def list_handover(filters: Optional[Dict[str, Any]] = None) -> QuerySet[Handover]:
    filters = filters or {}
    qs = Handover.objects.using(ERP_DB_ALIAS).all()
    if (v := filters.get("employee_id")) is not None:
        qs = qs.filter(employee_id=v)
    if (v := filters.get("manager_id")) is not None:
        qs = qs.filter(manager_id=v)
    if (v := filters.get("receiver_employee_id")) is not None:
        qs = qs.filter(receiver_employee_id=v)
    if (v := filters.get("status")) is not None:
        qs = qs.filter(status=v)
    return qs.order_by("-created_at").prefetch_related("items")

def get_handover(handover_id: int) -> Handover:
    return Handover.objects.using(ERP_DB_ALIAS).get(id=handover_id)

def get_item(item_id: int) -> HandoverItem:
    return HandoverItem.objects.using(ERP_DB_ALIAS).get(id=item_id)

# ========================= Mutations (ghi) =========================
def create_handover(**data) -> Handover:
    with transaction.atomic(using=ERP_DB_ALIAS):
        return Handover.objects.using(ERP_DB_ALIAS).create(**data)

def update_handover_status(handover_id: int, status: int) -> Handover:
    with transaction.atomic(using=ERP_DB_ALIAS):
        ho = _maybe_for_update(Handover.objects.using(ERP_DB_ALIAS)).get(id=handover_id)
        ho.status = status
        ho.save(using=ERP_DB_ALIAS, update_fields=["status", "updated_at"])
        return ho

def add_item(handover_id: int, *, title: str, detail: str = "", assignee_id: Optional[int] = None) -> HandoverItem:
    """
    FIX lõi: tạo item bằng handover_id (int) → gán FK bằng 'handover_id=handover_id'
    Tránh truyền object vào _id.
    """
    with transaction.atomic(using=ERP_DB_ALIAS):
        it = HandoverItem.objects.using(ERP_DB_ALIAS).create(
            handover_id=handover_id,
            title=title,
            detail=detail or "",
            assignee_id=assignee_id,
            # để repo không phụ thuộc enum, fallback về 0 nếu model không có enum
            status=getattr(HandoverItem.ItemStatus, "PENDING", 0),
        )
        # Đồng bộ trạng thái handover: nếu đang OPEN → IN_PROGRESS
        try:
            ho = get_handover(handover_id)
            if ho.status == getattr(Handover.Status, "OPEN", 0):
                ho.status = getattr(Handover.Status, "IN_PROGRESS", 1)
                ho.save(using=ERP_DB_ALIAS, update_fields=["status", "updated_at"])
        except Exception:
            pass
        return it

def set_item_status(item_id: int, status: int) -> HandoverItem:
    """
    Update trạng thái item; đồng bộ trạng thái Handover:
    - nếu tất cả DONE → Handover = DONE
    - nếu có item mà Handover còn OPEN → Handover = IN_PROGRESS
    """
    with transaction.atomic(using=ERP_DB_ALIAS):
        qs = HandoverItem.objects.using(ERP_DB_ALIAS).select_related("handover")
        qs = _maybe_for_update(qs)
        item = qs.get(id=item_id)

        item.status = status
        item.done_at = timezone.now() if status == getattr(HandoverItem.ItemStatus, "DONE", 1) else None
        item.save(using=ERP_DB_ALIAS, update_fields=["status", "done_at", "updated_at"])

        ho = item.handover
        total = ho.items.using(ERP_DB_ALIAS).count()
        done = ho.items.using(ERP_DB_ALIAS).filter(status=getattr(HandoverItem.ItemStatus, "DONE", 1)).count()

        if total and done == total:
            if ho.status != getattr(Handover.Status, "DONE", 2):
                ho.status = getattr(Handover.Status, "DONE", 2)
                ho.save(using=ERP_DB_ALIAS, update_fields=["status", "updated_at"])
        else:
            if ho.status == getattr(Handover.Status, "OPEN", 0):
                ho.status = getattr(Handover.Status, "IN_PROGRESS", 1)
                ho.save(using=ERP_DB_ALIAS, update_fields=["status", "updated_at"])

        return item
