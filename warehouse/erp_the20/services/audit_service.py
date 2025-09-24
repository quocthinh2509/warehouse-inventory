from django.utils import timezone
from erp_the20.models import AuditLog

def log_action(*, actor, action: str, object_type: str, object_id: str, before=None, after=None, ip=None):
    AuditLog.objects.create(
        actor=actor, action=action, object_type=object_type, object_id=str(object_id),
        before=before, after=after, ip=ip
    )