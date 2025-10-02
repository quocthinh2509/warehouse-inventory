# ============================================
# jira/models/comment.py
# ============================================
from django.db import models


class Comment(models.Model):
    issue = models.ForeignKey(
        'Issue',
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author_id = models.UUIDField(db_index=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['issue', 'created_at']),
        ]

    def __str__(self):
        return f"Comment on {self.issue.key}"