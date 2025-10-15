from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from django.db.models import Q, CheckConstraint
from .mixins import TimeStampedModel

class Attendance(TimeStampedModel):
    class Source(models.IntegerChoices):
        WEB = 0, "Web"
        MOBILE = 1, "Mobile"
        LARK = 2, "Lark"
        GOOGLE_FORMS = 3, "Google Forms"

    class WorkMode(models.IntegerChoices):
        ONSITE = 0, "Onsite (Văn phòng)"
        REMOTE = 1, "Remote (Online)"

    class Status(models.IntegerChoices):
        PENDING = 0, "Pending"
        APPROVED = 1, "Approved"
        REJECTED = 2, "Rejected"
        CANCELED = 3, "Canceled"

    employee_id = models.IntegerField(null=True, blank=True, db_index=True)
    shift_template = models.ForeignKey("erp_the20.ShiftTemplate", null=False, blank=False, on_delete=models.PROTECT)
    on_leave = models.ForeignKey("erp_the20.LeaveRequest", null=True, blank=True, on_delete=models.SET_NULL)

    date = models.DateField(null=False, blank=False, db_index=True)
    ts_in = models.DateTimeField(null=True, blank=True)
    ts_out = models.DateTimeField(null=True, blank=True)

    source = models.IntegerField(choices=Source.choices, default=Source.WEB)
    work_mode = models.IntegerField(choices=WorkMode.choices, default=WorkMode.ONSITE)

    bonus = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Tiền thưởng/bonus cho phiên làm việc (nếu có)."
    )

    status = models.IntegerField(choices=Status.choices, default=Status.PENDING)
    is_valid = models.BooleanField(default=False, help_text="True khi đã duyệt hợp lệ")

    requested_by = models.IntegerField(null=True, blank=True)
    requested_at = models.DateTimeField(default=timezone.now, editable=False)

    approved_by = models.IntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=255, blank=True, default="")

    worked_minutes = models.IntegerField(default=0, help_text="Số phút làm thực tế (đã trừ break trong ca nếu áp dụng)")
    paid_minutes   = models.IntegerField(default=0, help_text="Số phút được tính lương (đã áp hệ số/loại trừ)")

    raw_payload = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "Attendance"
        ordering = ["date", "ts_in"]
        constraints = [
            CheckConstraint(
                name="attn_approved_requires_is_valid_true",
                check=Q(status=1) & Q(is_valid=True) | ~Q(status=1),
            ),
            CheckConstraint(
                name="attn_ts_out_gte_ts_in_when_both_set",
                check=Q(ts_out__isnull=True) | Q(ts_in__isnull=True) | Q(ts_out__gte=models.F("ts_in")),
            ),
        ]
        indexes = [
            models.Index(fields=["employee_id", "date"]),
            models.Index(fields=["status", "is_valid"]),
            models.Index(fields=["shift_template"]),
            models.Index(fields=["source"]),
            models.Index(fields=["work_mode"]),
        ]
        unique_together = [("employee_id", "date", "shift_template")]

    def approve(self, manager_user_id: int):
        self.status = self.Status.APPROVED
        self.is_valid = True
        self.approved_by = manager_user_id
        self.approved_at = timezone.now()

    def reject(self, manager_user_id: int, reason: str = ""):
        self.status = self.Status.REJECTED
        self.is_valid = False
        self.approved_by = manager_user_id
        self.approved_at = timezone.now()
        self.reject_reason = reason or ""

    def __str__(self):
        return f"ATTD {self.employee_id} {self.date} [{self.get_status_display()}]"
