from django.db import models
from django.db.models import Q, UniqueConstraint
from .mixins import TimeStampedModel

class Department(TimeStampedModel):
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]
        db_table = "Department"
        constraints = [
            UniqueConstraint(fields=["code"], condition=Q(deleted_at__isnull=True), name="uniq_active_department_code")
        ]

    def __str__(self):
        return self.name

class Position(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["name"]
        db_table = "Position"
        constraints = [
            UniqueConstraint(fields=["code"], condition=Q(deleted_at__isnull=True), name="uniq_active_position_code")
        ]

    def __str__(self):
        return self.name
