from typing import Optional
from django.db import transaction, connection
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet
from django.utils import timezone
from erp_the20.models import Proposal

def create_proposal(**fields) -> Proposal:
    return Proposal.objects.create(**fields)

def get_proposal(pk: int) -> Proposal:
    return get_object_or_404(Proposal, pk=pk)

def filter_proposals(
    *, employee_id: Optional[int] = None, manager_id: Optional[int] = None,
    status: Optional[int] = None, type_: Optional[int] = None
) -> QuerySet:
    qs = Proposal.objects.all().order_by("-created_at")
    if employee_id is not None:
        qs = qs.filter(employee_id=employee_id)
    if manager_id is not None:
        qs = qs.filter(manager_id=manager_id)
    if status is not None:
        qs = qs.filter(status=status)
    if type_ is not None:
        qs = qs.filter(type=type_)
    return qs

@transaction.atomic
def set_status(proposal_id: int, status: int, note: str = "") -> Proposal:
    """
    Dùng SELECT ... FOR UPDATE khi có thể; nếu không, fallback sang UPDATE thường.
    Tránh TransactionManagementError trên SQLite/hoặc khi ngoài atomic.
    """
    can_lock = bool(getattr(connection.features, "supports_select_for_update", False)) and connection.in_atomic_block
    if can_lock:
        p = Proposal.objects.select_for_update().get(pk=proposal_id)
        p.status = status
        p.decision_note = note or ""
        p.save(update_fields=["status", "decision_note", "updated_at"])
        return p
    else:
        # Fallback: cập nhật trực tiếp
        Proposal.objects.filter(pk=proposal_id).update(
            status=status,
            decision_note=note or "",
            updated_at=timezone.now(),
        )
        return Proposal.objects.get(pk=proposal_id)

@transaction.atomic
def update_decision_note(proposal_id: int, note: str) -> Proposal:
    can_lock = bool(getattr(connection.features, "supports_select_for_update", False)) and connection.in_atomic_block
    if can_lock:
        p = Proposal.objects.select_for_update().get(pk=proposal_id)
        p.decision_note = note or ""
        p.save(update_fields=["decision_note", "updated_at"])
        return p
    else:
        Proposal.objects.filter(pk=proposal_id).update(
            decision_note=note or "",
            updated_at=timezone.now(),
        )
        return Proposal.objects.get(pk=proposal_id)
