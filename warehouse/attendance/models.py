from django.db import models

class AllowedIP(models.Model):
    ip = models.CharField(max_length=64, unique=True)
    note = models.CharField(max_length=200, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ip

class Attendance(models.Model):
    user_id = models.CharField(max_length=100)
    action = models.CharField(max_length=50)  # checkin / checkout
    ip_from_client = models.CharField(max_length=64, blank=True, null=True)
    ip_from_request = models.CharField(max_length=64)
    allowed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.created_at} {self.user_id} {self.action} allowed={self.allowed}"
