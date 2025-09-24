from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.conf import settings


class WifiVerifier(models.Model):
    verifier_id = models.CharField(max_length=64, unique=True)
    public_key_pem = models.TextField()  # paste nguyên nội dung verifier_public.pem
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.verifier_id} ({'active' if self.is_active else 'inactive'})"

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
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self): return self.name


class Worksite(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    address = models.TextField(blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    radius_m = models.IntegerField(default=200, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self): return self.name


class Position(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    default_department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["name"]

    def __str__(self): return self.name


class Employee(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    full_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    position = models.ForeignKey(Position, null=True, blank=True, on_delete=models.SET_NULL)
    default_worksite = models.ForeignKey(Worksite, null=True, blank=True, on_delete=models.SET_NULL)
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
    weekly_days = models.CharField(max_length=20, blank=True)  # ví dụ: "1,2,3,4,5" (Thứ 2 đến Thứ 6) dùng để tạo lịch tuần
    default_worksite = models.ForeignKey(Worksite, null=True, blank=True, on_delete=models.SET_NULL) # nơi làm việc mặc định

    class Meta:
        ordering = ["code"]

    def __str__(self): return f"{self.code} - {self.name}"

""" Mục đích: 1 ca cụ thể vào một ngày cụ thể (được tạo từ template).

Trường chính:

template + date + worksite → unique_together (không bị trùng ca cùng ngày/địa điểm).

status: open/closed/canceled kiểm soát đăng ký/assign.
"""
class ShiftInstance(TimeStampedModel): # ca làm việc cụ thể
    template = models.ForeignKey(ShiftTemplate, on_delete=models.PROTECT) 
    date = models.DateField()
    worksite = models.ForeignKey(Worksite, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=16, default="open")  # open/closed/canceled

    class Meta:
        unique_together = [("template", "date", "worksite")]
        ordering = ["-date", "template_id"]


class ShiftAssignment(TimeStampedModel):# gán ca cho nhân viên cụ thể , quản lý hoặc hr sẽ gán ca
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên được gán ca
    shift_instance = models.ForeignKey(ShiftInstance, on_delete=models.PROTECT) # ca cụ thể được gán
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="shift_assignments"
    )
    status = models.CharField(max_length=16, default="assigned")  # assigned/dropped/completed

    class Meta:
        unique_together = [("employee", "shift_instance")]
        ordering = ["shift_instance_id"]


class ShiftRegistration(TimeStampedModel): # đăng ký ca (nhân viên tự đăng ký ca trống)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên đăng ký ca
    shift_instance = models.ForeignKey(ShiftInstance, on_delete=models.PROTECT) # ca cụ thể được đăng ký
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

Định vị:

lat/lng/accuracy_m: vị trí và độ chính xác

worksite_detected & distance_to_worksite_m: worksite hệ thống xác định gần nhất và khoảng cách → phục vụ rule hợp lệ/không.

Hợp lệ: is_valid + reject_reason nếu vi phạm (sai vị trí, duplicate, quá xa cửa sổ thời gian…).

raw_payload: lưu nguyên data client gửi (mobile/lark/web) phục vụ audit.


    """
    EVENT_TYPES = (("check_in", "check_in"), ("check_out", "check_out"))
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên checkin/checkout
    shift_instance = models.ForeignKey(ShiftInstance, null=True, blank=True, on_delete=models.SET_NULL) # ca làm việc liên quan (nếu có)
    event_type = models.CharField(max_length=16, choices=EVENT_TYPES) # check_in/check_out
    ts = models.DateTimeField() # thời gian checkin/checkout
    lat = models.FloatField(null=True, blank=True) # kinh độ
    lng = models.FloatField(null=True, blank=True) # vĩ độ
    accuracy_m = models.FloatField(null=True, blank=True) # độ chính xác (mét)
    source = models.CharField(max_length=16, default="web")  # web/mobile/lark nền tảng check in check out
    worksite_detected = models.ForeignKey(Worksite, null=True, blank=True, on_delete=models.SET_NULL) # nơi làm việc phát hiện (dựa trên toạ độ)
    distance_to_worksite_m = models.FloatField(null=True, blank=True) # khoảng cách đến nơi làm việc (mét)
    is_valid = models.BooleanField(default=True) # checkin/checkout hợp lệ (dựa trên quy tắc)
    reject_reason = models.TextField(blank=True) # lý do không hợp lệ (nếu có)
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

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên
    date = models.DateField() # ngày (không có thời gian)
    planned_minutes = models.IntegerField(default=0) # phút làm việc dự kiến
    worked_minutes = models.IntegerField(default=0) # phút làm việc thực tế
    late_minutes = models.IntegerField(default=0) # phút đi muộn
    early_leave_minutes = models.IntegerField(default=0) # phút về sớm
    overtime_minutes = models.IntegerField(default=0) # phút làm thêm
    status = models.CharField(max_length=16, default="present")  # present/absent/leave/holiday
    notes = models.TextField(blank=True) # ghi chú (nếu có)

    class Meta:
        unique_together = [("employee", "date")]
        ordering = ["-date"]


"""
AttendanceCorrection

Yêu cầu sửa công: thiếu check-in/out, sai worksite, đổi trạng thái…

Có quy trình duyệt (pending/approved/rejected), changeset mô tả thay đổi.
"""
class AttendanceCorrection(TimeStampedModel):

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT) # nhân viên yêu cầu sửa công
    date = models.DateField() # ngày cần sửa
    type = models.CharField(max_length=32)  # missing_check_in/out, wrong_worksite, etc.
    requested_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL) # người tạo yêu cầu (có thể là nhân viên hoặc quản lý/HR tạo hộ)
    status = models.CharField(max_length=16, default="pending")  # pending/approved/rejected
    approver = models.ForeignKey("auth.User", null=True, blank=True, related_name="+", on_delete=models.SET_NULL) # người duyệt
    changeset = models.JSONField() # mô tả thay đổi (vd: {"check_in": "2024-10-01T09:05:00Z", "worksite": 3})

    class Meta:
        ordering = ["-created_at"]


# ===== Leave =====
class LeaveType(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True) # mã loại phép
    name = models.CharField(max_length=120) # tên loại phép
    paid = models.BooleanField(default=True) # có lương hay không
    annual_quota_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00")) # số ngày phép năm
    carry_over_rule = models.CharField(max_length=64, blank=True) # quy tắc chuyển phép (nếu có)
    requires_attachment = models.BooleanField(default=False) # có yêu cầu đính kèm (vd: giấy khám bệnh)

    class Meta:
        ordering = ["code"]

    def __str__(self): return f"{self.code} - {self.name}"


class LeaveBalance(TimeStampedModel): # số dư phép
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    period = models.CharField(max_length=4)  # YYYY
    opening = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    accrued = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    used = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    carry_in = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    carry_out = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    closing = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        unique_together = [("employee", "leave_type", "period")]
        ordering = ["-period"]


class LeaveRequest(TimeStampedModel): # đơn xin nghỉ phép
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField() # ngày bắt đầu nghỉ
    end_date = models.DateField() # ngày kết thúc nghỉ
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # số giờ nghỉ (nếu nghỉ nửa ngày)
    reason = models.TextField(blank=True)  # lý do nghỉ
    attachment = models.FileField(upload_to="leave_attachments/", null=True, blank=True) # tệp đính kèm (nếu có)
    status = models.CharField(max_length=16, default="pending")  # pending/approved/rejected/canceled
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
