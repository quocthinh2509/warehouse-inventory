from django.db import models
from .mixins import TimeStampedModel

class Proposal(TimeStampedModel):
    class Type(models.IntegerChoices):
        RESIGN = 0, "Resign"
        SALARY_INCREASE = 1, "Salary Increase"
        CONTRIBUTION = 2, "Contribution"

    class Status(models.IntegerChoices):
        NEW = 0, "New"
        APPROVED = 1, "Approved"
        REJECTED = 2, "Rejected"

    employee_id = models.IntegerField(db_index=True)
    manager_id = models.IntegerField(null=True, blank=True, db_index=True)
    type = models.IntegerField(choices=Type.choices)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, default="")
    status = models.IntegerField(choices=Status.choices, default=Status.NEW)
    decision_note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "Proposal"
        ordering = ["-created_at"]
