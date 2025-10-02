# ============================================
# jira/models/issue.py
# ============================================
from django.db import models


class Issue(models.Model):
    class IssueType(models.TextChoices):
        TASK = 'TASK', 'Task'
        BUG = 'BUG', 'Bug'
        STORY = 'STORY', 'Story'
        EPIC = 'EPIC', 'Epic'

    class Priority(models.TextChoices):
        LOWEST = 'LOWEST', 'Lowest'
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        HIGHEST = 'HIGHEST', 'Highest'

    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='issues'
    )
    key = models.CharField(max_length=20, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    issue_type = models.CharField(max_length=10, choices=IssueType.choices)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    status = models.ForeignKey(
        'Status',
        on_delete=models.PROTECT,
        related_name='issues'
    )
    assignee_id = models.UUIDField(null=True, blank=True, db_index=True)
    reporter_id = models.UUIDField(db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks'
    )
    sprint = models.ForeignKey(
        'Sprint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issues'
    )
    estimate = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'issues'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['assignee_id']),
            models.Index(fields=['reporter_id']),
            models.Index(fields=['sprint']),
        ]

    def __str__(self):
        return f"{self.key} - {self.title}"
