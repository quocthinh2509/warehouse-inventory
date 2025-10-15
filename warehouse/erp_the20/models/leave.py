from django.db import models
from django.db.models import Q, CheckConstraint
from .mixins import TimeStampedModel

class LeaveRequest(TimeStampedModel):
    class Status(models.IntegerChoices):
        SUBMITTED = 0, "Submitted"
        APPROVED = 1, "Approved"
        REJECTED = 2, "Rejected"
        CANCELLED = 3, "Cancelled"

    class LeaveType(models.IntegerChoices):
        ANNUAL = 0, "Nghỉ phép năm"
        UNPAID = 1, "Nghỉ không phép"
        SICK = 2, "Nghỉ ốm"
        PAID_SPECIAL = 3, "Nghỉ chế độ hưởng nguyên lương (kết hôn, tang lễ, v.v.)"
        OVERTIME = 4, "Tăng ca"
        ONLINE = 5, "Làm online"
        SHIFT_CHANGE = 6, "Đổi ca làm"
        LATE_IN = 7, "Đi làm muộn"
        EARLY_OUT = 8, "Về sớm"

    paid = models.BooleanField(default=False, help_text="Đơn này có được tính lương hay không.")
    employee_id = models.IntegerField(null=True, blank=True, db_index=True)

    start_date = models.DateField()
    end_date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    leave_type = models.IntegerField(choices=LeaveType.choices)
    reason = models.TextField(blank=True)

    status = models.IntegerField(choices=Status.choices, default=Status.SUBMITTED)
    decision_ts = models.DateTimeField(null=True, blank=True)
    decided_by = models.IntegerField(null=True, blank=True)

    handover_to_employee_id = models.IntegerField(null=True, blank=True, db_index=True,
        help_text="Employee ID được bàn giao (có thể null)")
    handover_content = models.TextField(null=True, blank=True, help_text="Nội dung bàn giao (có thể null)")

    class Meta:
        ordering = ["-created_at"]
        db_table = "LeaveRequest"
        constraints = [
            CheckConstraint(name="leave_dates_valid", check=Q(end_date__gte=models.F("start_date"))),
            CheckConstraint(
                name="leave_handover_not_self",
                check=Q(handover_to_employee_id__isnull=True) | ~Q(handover_to_employee_id=models.F("employee_id")),
            ),
        ]

    def __str__(self):
        return f"LV {self.employee_id} {self.get_leave_type_display()} {self.start_date}→{self.end_date} [{self.get_status_display()}]"
