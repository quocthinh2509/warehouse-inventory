from django.db import models
from .mixins import TimeStampedModel

class AuditLog(TimeStampedModel):
    actor = models.IntegerField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "AuditLog"
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["actor"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.object_type}#{self.object_id} by {self.actor}"
