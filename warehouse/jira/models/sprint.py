# ============================================
# jira/models/sprint.py
# ============================================
from django.db import models


class Sprint(models.Model):
    class SprintStatus(models.TextChoices):
        FUTURE = 'FUTURE', 'Future'
        ACTIVE = 'ACTIVE', 'Active'
        CLOSED = 'CLOSED', 'Closed'

    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='sprints'
    )
    name = models.CharField(max_length=255)
    goal = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=SprintStatus.choices,
        default=SprintStatus.FUTURE
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sprints'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
        ]

    def __str__(self):
        return f"{self.project.key} - {self.name}"
