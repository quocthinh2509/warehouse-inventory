from django.db import models
from .mixins import TimeStampedModel

class Handover(TimeStampedModel):
    class Status(models.IntegerChoices):
        OPEN = 0, "Open"
        IN_PROGRESS = 1, "In Progress"
        DONE = 2, "Done"
        CANCELLED = 3, "Cancelled"

    employee_id = models.IntegerField(db_index=True)
    manager_id = models.IntegerField(null=True, blank=True, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.IntegerField(choices=Status.choices, default=Status.OPEN)
    receiver_employee_id = models.IntegerField(null=True, blank=True, db_index=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "Handover"
        ordering = ["-created_at"]

class HandoverItem(TimeStampedModel):
    class ItemStatus(models.IntegerChoices):
        PENDING = 0, "Pending"
        DONE = 1, "Done"

    handover = models.ForeignKey(Handover, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True, default="")
    assignee_id = models.IntegerField(null=True, blank=True, db_index=True)
    status = models.IntegerField(choices=ItemStatus.choices, default=ItemStatus.PENDING)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "HandoverItem"
        ordering = ["created_at"]
