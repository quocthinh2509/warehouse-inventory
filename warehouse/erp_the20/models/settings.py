from django.db import models
from .mixins import TimeStampedModel

class HolidayCalendar(TimeStampedModel):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["-date"]
        db_table = "HolidayCalendar"
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.date} - {self.name}"

class ApprovalFlow(TimeStampedModel):
    object_type = models.CharField(max_length=32)
    role = models.CharField(max_length=32)
    step = models.IntegerField(default=1)

    class Meta:
        db_table = "ApprovalFlow"
        unique_together = [("object_type", "role", "step")]
        ordering = ["object_type", "step"]
        indexes = [models.Index(fields=["object_type", "role"])]

    def __str__(self):
        return f"{self.object_type} - {self.role} - step {self.step}"
