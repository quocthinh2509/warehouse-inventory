from typing import Iterable, Optional, Dict, Any, List
from django.utils import timezone
from django.db.models import Q, QuerySet
from erp_the20.models import Notification

def create_notification(
    title: str,
    *,
    recipients: Optional[Iterable[int]] = None,
    to_user: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    object_type: str = "",
    object_id: str = "",
    channel: int = Notification.Channel.INAPP,
    delivered: bool = True,
) -> Notification:
    return Notification.objects.create(
        title=title,
        recipients=list(recipients) if recipients else None,
        to_user=to_user,
        payload=payload or {},
        object_type=object_type,
        object_id=object_id,
        channel=channel,
        delivered=delivered,
        delivered_at=timezone.now() if delivered else None,
        attempt_count=1 if delivered else 0,
    )

def list_by_user(user_id: int, limit: int = 200) -> QuerySet:
    return (
        Notification.objects
        .filter(Q(to_user=user_id) | Q(recipients__contains=[user_id]))
        .order_by("-created_at")[:limit]
    )
