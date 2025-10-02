# ============================================
# jira/models/history.py
# ============================================
from django.db import models


class IssueHistory(models.Model):
    issue = models.ForeignKey(
        'Issue',
        on_delete=models.CASCADE,
        related_name='history'
    )
    user_id = models.UUIDField(db_index=True)
    field_name = models.CharField(max_length=50)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'issue_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['issue', '-created_at']),
        ]

    def __str__(self):
        return f"{self.issue.key} - {self.field_name} changed"