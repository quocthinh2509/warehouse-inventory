from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Q, CheckConstraint, UniqueConstraint
from decimal import Decimal


# =========================
# Base
# =========================
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Soft delete: set thời điểm xóa; query active: filter(deleted_at__isnull=True)
    deleted_at = models.DateTimeField(null=True, blank=True, default=None, db_index=True)

    class Meta:
        abstract = True


# =========================
# Core Master
# =========================
class Department(TimeStampedModel):
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]
        db_table = "Department"
        constraints = [
            UniqueConstraint(fields=["code"], condition=Q(deleted_at__isnull=True), name="uniq_active_department_code")
        ]

    def __str__(self):
        return self.name


class Position(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["name"]
        db_table = "Position"
        constraints = [
            UniqueConstraint(fields=["code"], condition=Q(deleted_at__isnull=True), name="uniq_active_position_code")
        ]

    def __str__(self):
        return self.name


# =========================
# Shifts & Scheduling (mẫu ca làm)
# =========================
class ShiftTemplate(TimeStampedModel):
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=120)
    start_time = models.TimeField() # thời gian bắt đầu ca
    end_time = models.TimeField() # thời gian kết thúc ca
    break_minutes = models.IntegerField(default=0) # phút nghỉ giữa ca
    overnight = models.BooleanField(default=False) # ca qua đêm (kết thúc ngày hôm sau)
    pay_factor = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Hệ số cho ca (ví dụ: ca đêm 1.5)"
    )

    class Meta:
        ordering = ["code"]
        db_table = "ShiftTemplate"
        constraints = [
            UniqueConstraint(
                fields=["code"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_active_shifttemplate_code",
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


# =========================
# Leave / Requests
# =========================
class LeaveRequest(TimeStampedModel):
    """
    Đơn nghỉ / thay đổi liên quan đến thời gian làm việc.
    Người nộp đơn chính là employee_id. Mọi quyết định dùng chung decided_by.
    Dùng IntegerChoices để lưu int trong DB.
    """
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

    # Nếu xin theo ngày
    start_date = models.DateField()
    end_date = models.DateField()

    # Nếu xin theo giờ (tùy chọn, để trống nếu dùng theo ngày)
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    leave_type = models.IntegerField(choices=LeaveType.choices)
    reason = models.TextField(blank=True)

    status = models.IntegerField(choices=Status.choices, default=Status.SUBMITTED)
    decision_ts = models.DateTimeField(null=True, blank=True)
    decided_by = models.IntegerField(null=True, blank=True)

    handover_to_employee_id = models.IntegerField( # người được bàn giao
        null=True, blank=True, db_index=True,
        help_text="Employee ID được bàn giao (có thể null)"
    )
    handover_content = models.TextField( # công việc được bàn giao
        null=True, blank=True,
        help_text="Nội dung bàn giao (có thể null)"
    )



    class Meta:
        ordering = ["-created_at"]
        db_table = "LeaveRequest"

        constraints = [
            CheckConstraint(
                name="leave_dates_valid",
                check=Q(end_date__gte=models.F("start_date")),
            ),
            # không được bàn giao cho chính mình
            CheckConstraint(
                name="leave_handover_not_self",
                check=Q(handover_to_employee_id__isnull=True) |
                      ~Q(handover_to_employee_id=models.F("employee_id")),
            ),
        ]

    def __str__(self):
        return f"LV {self.employee_id} {self.get_leave_type_display()} {self.start_date}→{self.end_date} [{self.get_status_display()}]"


# =========================
# Attendance (thay cho AttendanceSummary / bỏ ShiftInstance)
# =========================
class Attendance(TimeStampedModel):
    """
    Một bản ghi chấm công cho nhân viên theo NGÀY,
    gắn với mẫu ca (ShiftTemplate) và các mốc in/out.
    Dùng IntegerChoices để lưu int trong DB.
    """
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

    # gắn với employee & mẫu ca
    employee_id = models.IntegerField(null=True, blank=True, db_index=True)  # thay vì FK Employee
    shift_template = models.ForeignKey(ShiftTemplate, null=False, blank=False, on_delete=models.PROTECT)

    # nếu nghỉ: liên kết tới đơn nghỉ
    on_leave = models.ForeignKey(LeaveRequest, null=True, blank=True, on_delete=models.SET_NULL)

    # ngày làm việc & thời gian ra/vào ca
    date = models.DateField(null=False, blank=False, db_index=True)
    ts_in = models.DateTimeField(null=True, blank=True)
    ts_out = models.DateTimeField(null=True, blank=True)

    # nguồn & chế độ làm việc (enum số)
    source = models.IntegerField(choices=Source.choices, default=Source.WEB)
    work_mode = models.IntegerField(choices=WorkMode.choices, default=WorkMode.ONSITE)

    # tiền thưởng/chi phí phát sinh trên phiên làm việc
    bonus = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal("0.00"),
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

    # Tính toán (số phút)
    worked_minutes = models.IntegerField(default=0, help_text="Số phút làm thực tế (đã trừ break trong ca nếu áp dụng)")
    paid_minutes   = models.IntegerField(default=0, help_text="Số phút được tính lương (đã áp hệ số/loại trừ)")

    raw_payload = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "Attendance"
        ordering = ["date", "ts_in"]
        constraints = [
            # Approved thì is_valid phải True
            CheckConstraint(
                name="attn_approved_requires_is_valid_true",
                check=Q(status=1) & Q(is_valid=True) | ~Q(status=1),
            ),
            # Nếu có cả in/out thì out phải >= in
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
        # Bật nếu muốn 1 nhân viên chỉ có 1 attendance/ca/ngày:
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

# =========================
# Settings / Audit / Notifications
# =========================
class HolidayCalendar(TimeStampedModel):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["-date"]
        db_table = "HolidayCalendar"
        indexes = [
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.date} - {self.name}"


class ApprovalFlow(TimeStampedModel):
    object_type = models.CharField(max_length=32)   # vd: "leave_request", "attendance", ...
    role = models.CharField(max_length=32)          # vd: "manager", "hr", ...
    step = models.IntegerField(default=1)

    class Meta:
        db_table = "ApprovalFlow"
        unique_together = [("object_type", "role", "step")]
        ordering = ["object_type", "step"]
        indexes = [
            models.Index(fields=["object_type", "role"]),
        ]

    def __str__(self):
        return f"{self.object_type} - {self.role} - step {self.step}"


class Notification(TimeStampedModel):
    class Channel(models.IntegerChoices):
        INAPP = 0, "In-app"
        EMAIL = 1, "Email"
        SMS   = 2, "SMS"
        LARK  = 3, "Lark"   # << thêm Lark

    # Liên kết ngữ cảnh (để truy vết)
    object_type = models.CharField(max_length=64, blank=True, default="", help_text="vd: leave_request, attendance, ...")
    object_id   = models.CharField(max_length=64, blank=True, default="", help_text="ID đối tượng liên quan (string)")

    # Thông tin người nhận
    to_user         = models.IntegerField(null=True, blank=True, db_index=True)  # employee_id
    to_email        = models.CharField(max_length=254, blank=True, default="")
    to_lark_user_id = models.CharField(max_length=64, blank=True, default="", help_text="open_id Lark nếu có")

    # Nội dung & kênh
    channel = models.IntegerField(choices=Channel.choices, default=Channel.INAPP, db_index=True)
    title   = models.CharField(max_length=200)
    #body    = models.TextField()
    payload = models.JSONField(null=True, blank=True, help_text="Raw payload đã gửi (mask thông tin nhạy cảm)")

    # Kết quả gửi
    delivered     = models.BooleanField(default=False, db_index=True)
    delivered_at  = models.DateTimeField(null=True, blank=True)
    attempt_count = models.IntegerField(default=0)
    last_error    = models.TextField(blank=True, default="")

    # Ghi nhận từ provider
    provider_message_id  = models.CharField(max_length=128, blank=True, default="")
    provider_status_code = models.CharField(max_length=32, blank=True, default="")
    provider_response    = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "Notification"

    def __str__(self):
        state = "sent" if self.delivered else "pending/failed"
        return f"NOTI[{self.get_channel_display()}] to_user={self.to_user or '-'} ({state})"



class AuditLog(TimeStampedModel):
    actor = models.IntegerField(null=True, blank=True, db_index=True)  # thay vì FK Employee
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "AuditLog"
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["actor"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.object_type}#{self.object_id} by {self.actor}"

