# ============================================
# jira/models/status.py
# ============================================
from django.db import models


class Status(models.Model):
    name = models.CharField(max_length=50)
    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='statuses'
    )
    order = models.IntegerField(default=0)
    is_done = models.BooleanField(default=False)

    class Meta:
        db_table = 'statuses'
        ordering = ['order']
        unique_together = ['name', 'project']
        indexes = [
            models.Index(fields=['project', 'order']),
        ]

    def __str__(self):
        return f"{self.project.key} - {self.name}"
