from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.contrib.postgres.fields import ArrayField

# ===== Base =====
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


# ===== Core Master =====
class Department(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    class Meta:
        ordering = ["name"]

    def __str__(self): return self.name


class Position(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL,null=True,blank=True) # phòng ban mặc định
    class Meta:
        ordering = ["name"]

    def __str__(self): return self.name


class Employee(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    user_name = models.CharField(max_length=64, unique=True) # liên kết với user hệ thống ngoài
    full_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    position = models.ForeignKey(Position, on_delete=models.SET_NULL,null=True,blank=True, related_name="employees")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self): return f"{self.code} - {self.full_name}"


# ===== Shifts & Scheduling =====
class ShiftTemplate(TimeStampedModel):   # mẫu ca làm việc
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    start_time = models.TimeField() # giờ bắt đầu ca làm việc
    end_time = models.TimeField() # giờ kết thúc ca làm việc
    break_minutes = models.IntegerField(default=0) # phút nghỉ giữa ca
    overnight = models.BooleanField(default=False) # ca qua đêm  true (VD: 22:00 - 06:00) / false (VD: 08:00 - 17:00)
    #weekly_days = models.JSONField(default=list)


    class Meta:
        ordering = ["code"]

    def __str__(self): return f"{self.code} - {self.name}"

""" Mục đích: 1 ca cụ thể vào một ngày cụ thể (được tạo từ template).

Trường chính:

template + date  → unique_together (không bị trùng ca cùng ngày/địa điểm).

status: open/closed/canceled kiểm soát đăng ký/assign.
"""
class ShiftInstance(TimeStampedModel): # ca làm việc cụ thể
    SHIFT_STATUS = [
    ("planned", "Planned"),
    ("active", "Active"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
    ]
    template = models.ForeignKey(ShiftTemplate, on_delete=models.PROTECT) 
    date = models.DateField()
    status = models.CharField(choices=SHIFT_STATUS, max_length=16, default="planned") # trạng thái ca

    class Meta:
        unique_together = [("template", "date")]
        ordering = ["-date", "template_id"]


class ShiftAssignment(TimeStampedModel):# gán ca cho nhân viên cụ thể , quản lý hoặc hr sẽ gán ca
    ASSIGN_STATUS = [
    ("assigned", "Assigned"),
    ("pending", "Pending"),
    ("cancelled", "Cancelled"),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên được gán ca
    shift_instance = models.ForeignKey(ShiftInstance, on_delete=models.CASCADE) # ca cụ thể được gán
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="shift_assignments"
    )
    status = models.CharField(choices=ASSIGN_STATUS, max_length=16, default="assigned")  # assigned/dropped/completed

    class Meta:
        unique_together = [("employee", "shift_instance")]
        ordering = ["shift_instance_id"]


class ShiftRegistration(TimeStampedModel): # đăng ký ca (nhân viên tự đăng ký ca trống)
    REGISTRATION_STATUS = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên đăng ký ca
    shift_instance = models.ForeignKey(ShiftInstance, on_delete=models.CASCADE) # ca cụ thể được đăng ký
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="shift_registrations"
    )
    status = models.CharField(max_length=16, default="pending")  # pending/approved/rejected
    reason = models.TextField(blank=True) # lý do đăng ký (nếu có)

    class Meta:
        unique_together = [("employee", "shift_instance")]
        ordering = ["-created_at"]


# ===== Attendance =====
class AttendanceEvent(TimeStampedModel):
    """
AttendanceEvent

Mỗi lần chấm: 1 bản ghi (type: check_in hoặc check_out).

Ghép với ca: shift_instance có thể null nếu chấm ngoài ca; có thể gán sau khi đối chiếu.


Hợp lệ: 

raw_payload: lưu nguyên data client gửi (mobile/lark/web) phục vụ audit.



    """
    SOURCE_CHOICES = [
        ("web", "Web"),
        ("mobile", "Mobile"),
        ("lark", "Lark"),
        ("googlefroms", "Google Forms"),
    ]
    EVENT_TYPES = (("in", "in"), ("out", "out"))
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên checkin/checkout
    shift_instance = models.ForeignKey(ShiftInstance, null=True, blank=True, on_delete=models.SET_NULL) # ca làm việc liên quan (nếu có)
    event_type = models.CharField(max_length=16, choices=EVENT_TYPES) #  in/out
    ts = models.DateTimeField() # thời gian checkin/checkout
    source = models.CharField(max_length=16,choices = SOURCE_CHOICES, default="web")  # web/mobile/lark nền tảng check in check out
    is_valid = models.BooleanField(default=True) # checkin/checkout hợp lệ (dựa trên quy tắc)
    raw_payload = models.JSONField(null=True, blank=True) # dữ liệu thô (nếu cần)

    class Meta:
        ordering = ["-ts"]


"""
AttendanceSummary

Bảng tổng hợp theo ngày / nhân viên (1 dòng/ngày/người).

Các cột: planned_minutes, worked_minutes, late_minutes, early_leave_minutes, overtime_minutes, status (present/absent/leave/holiday).

Sinh/ghi: sau khi có sự kiện check-in/out (và/hoặc cron cuối ngày) tính toán và upsert.
"""
class AttendanceSummary(TimeStampedModel):
    ATTENDANCE_STATUS = [
    ("present", "Present"),
    ("absent", "Absent"),
    ("late", "Late"),
    ("early_leave", "Early Leave"),
    ("working_remotely", "Working Remotely"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên
    date = models.DateField() # ngày (không có thời gian)
    planned_minutes = models.IntegerField(default=0) # phút làm việc dự kiến
    worked_minutes = models.IntegerField(default=0) # phút làm việc thực tế
    late_minutes = models.IntegerField(default=0) # phút đi muộn
    early_leave_minutes = models.IntegerField(default=0) # phút về sớm
    overtime_minutes = models.IntegerField(default=0) # phút làm thêm
    status = models.CharField(max_length=16,choices=ATTENDANCE_STATUS, default="absent")  # present/absent/leave/holiday
    notes = models.TextField(blank=True) # ghi chú (nếu có)
    segments = models.JSONField(default=list) # các đoạn làm việc (nếu cần)

    class Meta:
        unique_together = [("employee", "date")]
        ordering = ["-date"]


"""
AttendanceCorrection

Yêu cầu sửa công: thiếu check-in/out,  đổi trạng thái…

Có quy trình duyệt (pending/approved/rejected), changeset mô tả thay đổi.
"""
class AttendanceCorrection(TimeStampedModel):
    CORRECTION_STATUS = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên yêu cầu sửa công
    date = models.DateField() # ngày cần sửa
    type = models.CharField(max_length=32)  # missing_check_in/out, etc.
    requested_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL) # người tạo yêu cầu (có thể là nhân viên hoặc quản lý/HR tạo hộ)
    status = models.CharField(max_length=16, default="pending", choices = CORRECTION_STATUS)  # pending/approved/rejected
    approver = models.ForeignKey("auth.User", null=True, blank=True, related_name="+", on_delete=models.SET_NULL) # người duyệt
    changeset = models.JSONField() # mô tả thay đổi (vd: {"check_in": "2024-10-01T09:05:00Z"})

    class Meta:
        ordering = ["-created_at"]


# ===== Leave =====
class LeaveType(TimeStampedModel): # loại phép ( mẫu nghỉ phép)
    code = models.CharField(max_length=16, unique=True) # mã loại phép
    name = models.CharField(max_length=120) # tên loại phép
    paid = models.BooleanField(default=True) # có lương hay không
    annual_quota_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00")) # số ngày phép năm
    class Meta:
        ordering = ["code"]

    def __str__(self): return f"{self.code} - {self.name}"


class LeaveBalance(TimeStampedModel): # số dư phép
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT) # loại phép
    period = models.IntegerField()  # năm (ví dụ: "2024")
    opening = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00")) # số dư đầu kỳ
    accrued = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00")) # số ngày phép được tích lũy trong kỳ
    used = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00")) # số ngày phép đã sử dụng trong kỳ

    class Meta:
        unique_together = [("employee", "leave_type", "period")]
        ordering = ["-period"]


class LeaveRequest(TimeStampedModel): # đơn xin nghỉ phép
    LEAVE_REQUEST_STATUS = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField() # ngày bắt đầu nghỉ
    end_date = models.DateField() # ngày kết thúc nghỉ
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # số giờ nghỉ (nếu nghỉ nửa ngày)
    reason = models.TextField(blank=True)  # lý do nghỉ
    status = models.CharField(max_length=16, default="draft",choices = LEAVE_REQUEST_STATUS)  # pending/approved/rejected/canceled
    approver = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL) # người duyệt 
    decision_ts = models.DateTimeField(null=True, blank=True) # thời gian duyệt

    class Meta:
        ordering = ["-created_at"]


# ===== Settings / Audit / Notifications =====
class HolidayCalendar(TimeStampedModel): # ngày nghỉ lễ
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["-date"]


class ApprovalFlow(TimeStampedModel): # quy trình duyệt
    object_type = models.CharField(max_length=32)  # LeaveRequest/ShiftRegistration/AttendanceCorrection
    role = models.CharField(max_length=32)        # hr.manager, hr.admin, ...
    step = models.IntegerField(default=1)

    class Meta:
        unique_together = [("object_type", "role", "step")]
        ordering = ["object_type", "step"]


class Notification(TimeStampedModel): # thông báo
    to_user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=16, default="inapp")  # inapp/email/lark
    title = models.CharField(max_length=200)
    body = models.TextField()
    payload = models.JSONField(null=True, blank=True)
    delivered = models.BooleanField(default=False)


class AuditLog(TimeStampedModel): # nhật ký hoạt động
    actor = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
