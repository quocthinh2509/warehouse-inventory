from django.db import models
from .mixins import TimeStampedModel

class Notification(TimeStampedModel):
    class Channel(models.IntegerChoices):
        INAPP = 0, "In-app"
        EMAIL = 1, "Email"
        SMS   = 2, "SMS"
        LARK  = 3, "Lark"

    object_type = models.CharField(max_length=64, blank=True, default="", help_text="vd: leave_request, attendance, ...")
    object_id   = models.CharField(max_length=64, blank=True, default="", help_text="ID đối tượng liên quan (string)")

    to_user         = models.IntegerField(null=True, blank=True, db_index=True)
    to_email        = models.CharField(max_length=254, blank=True, default="")
    to_lark_user_id = models.CharField(max_length=64, blank=True, default="", help_text="open_id Lark nếu có")

    recipients = models.JSONField(null=True, blank=True, help_text="List[int] user_id")

    channel = models.IntegerField(choices=Channel.choices, default=Channel.INAPP, db_index=True)
    title   = models.CharField(max_length=200)
    payload = models.JSONField(null=True, blank=True, help_text="Raw payload đã gửi (mask thông tin nhạy cảm)")

    delivered     = models.BooleanField(default=False, db_index=True)
    delivered_at  = models.DateTimeField(null=True, blank=True)
    attempt_count = models.IntegerField(default=0)
    last_error    = models.TextField(blank=True, default="")

    provider_message_id  = models.CharField(max_length=128, blank=True, default="")
    provider_status_code = models.CharField(max_length=32, blank=True, default="")
    provider_response    = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "Notification"

    def __str__(self):
        state = "sent" if self.delivered else "pending/failed"
        return f"NOTI[{self.get_channel_display()}] to_user={self.to_user or '-'} ({state})"
