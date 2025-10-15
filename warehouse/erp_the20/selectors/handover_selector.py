# -*- coding: utf-8 -*-
from typing import Optional
from django.db.models import QuerySet
from erp_the20.models import Handover, HandoverItem

def handovers(employee_id: Optional[int] = None, manager_id: Optional[int] = None) -> QuerySet[Handover]:
    qs = Handover.objects.all().order_by("-created_at")
    if employee_id is not None:
        qs = qs.filter(employee_id=employee_id)
    if manager_id is not None:
        qs = qs.filter(manager_id=manager_id)
    return qs

def handover_items(handover_id: int) -> QuerySet[HandoverItem]:
    return HandoverItem.objects.filter(handover_id=handover_id).order_by("created_at")
