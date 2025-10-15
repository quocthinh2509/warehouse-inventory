from typing import Optional
from django.db.models import Q, QuerySet
from erp_the20.models import Notification

def notifications_for_user(user_id: int, limit: int = 200) -> QuerySet:
    return (
        Notification.objects
        .filter(Q(to_user=user_id) | Q(recipients__contains=[user_id]))
        .order_by("-created_at")[:limit]
    )

def notifications_search(object_type: Optional[str] = None) -> QuerySet:
    qs = Notification.objects.all().order_by("-created_at")
    if object_type:
        qs = qs.filter(object_type=object_type)
    return qs
