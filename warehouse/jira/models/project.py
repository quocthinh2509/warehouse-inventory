# ============================================
# jira/models/project.py
# ============================================
from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=255)
    key = models.CharField(max_length=10, unique=True, db_index=True)
    description = models.TextField(blank=True)
    owner_id = models.UUIDField(db_index=True)
    member_ids = models.JSONField(default=list)  # List of user IDs
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.key} - {self.name}"