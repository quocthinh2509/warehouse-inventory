from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal

# ====== Base ======
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

# ====== Nhân sự & Địa điểm ======
class Employee(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True) # userID từ tool hiện tại
    full_name = models.CharField(max_length=120) # tên đầy đủ
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00")) # lương cơ bản/tháng
    is_active = models.BooleanField(default=True)
    def __str__(self): return f"{self.code} - {self.full_name}"

class Worksite(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radius_m = models.PositiveIntegerField(default=150)
    def __str__(self): return f"{self.code} - {self.name}"

# ====== Ca làm & Kế hoạch ca (tối đa 3 ca/ngày, hỗ trợ qua đêm) ======
class ShiftTemplate(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.PositiveIntegerField(default=0)
    pay_coeff = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    is_overnight = models.BooleanField(default=False)
    def __str__(self): return f"{self.code} - {self.name}"

class ShiftPlan(TimeStampedModel):
    STATUS_CHOICES = [("draft","Draft"),("approved","Approved"),("changed","Changed")]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="shift_plans")
    date = models.DateField(db_index=True)
    slot = models.PositiveSmallIntegerField(default=1)  # 1..3
    template = models.ForeignKey(ShiftTemplate, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="approved")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("employee","date","slot")]
        indexes = [models.Index(fields=["employee","date"])]

    def __str__(self): return f"{self.employee.code} {self.date} {self.template.code} (slot {self.slot})"

    def start_dt(self, tz=None):
        tz = tz or timezone.get_current_timezone()
        return timezone.make_aware(datetime.combine(self.date, self.template.start_time), tz)

    def end_dt(self, tz=None):
        tz = tz or timezone.get_current_timezone()
        d = self.date + (timedelta(days=1) if self.template.is_overnight else timedelta(days=0))
        return timezone.make_aware(datetime.combine(d, self.template.end_time), tz)

    def clean(self):
        if self.slot not in (1,2,3):
            raise ValidationError("slot chỉ được 1, 2, hoặc 3.")
        tz = timezone.get_current_timezone()
        my_s, my_e = self.start_dt(tz), self.end_dt(tz)
        days = [self.date - timedelta(days=1), self.date, self.date + timedelta(days=1)]
        others = (ShiftPlan.objects.filter(employee=self.employee, date__in=days).exclude(pk=self.pk))
        for o in others:
            os, oe = o.start_dt(tz), o.end_dt(tz)
            if max(my_s, os) < min(my_e, oe):
                raise ValidationError(f"Chồng lấn ca với {o.date} slot {o.slot}.")

# ====== Chấm công ======
class AttendanceLog(TimeStampedModel):
    TYPE_CHOICES = [("IN","Check-in"),("OUT","Check-out")]
    SOURCE_CHOICES = [("web","Web"),("mobile","Mobile"),("api","API")]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="attendance_logs")
    worksite = models.ForeignKey(Worksite, on_delete=models.PROTECT, null=True, blank=True)
    shift_plan = models.ForeignKey(ShiftPlan, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    distance_m = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="web")
    device_id = models.CharField(max_length=64, blank=True)
    note = models.CharField(max_length=255, blank=True)
    is_valid = models.BooleanField(default=True)
    invalid_reason = models.CharField(max_length=255, blank=True)
    class Meta:
        indexes = [models.Index(fields=["employee","occurred_at"]), models.Index(fields=["type","occurred_at"])]
    def __str__(self): return f"{self.employee.code} {self.type} @ {self.occurred_at:%Y-%m-%d %H:%M:%S}"

# ====== Nghỉ phép ======
class LeaveType(TimeStampedModel):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    is_paid = models.BooleanField(default=True)  # có tính lương?
    default_unit = models.CharField(max_length=8, default="day")  # day|half|hour
    def __str__(self): return f"{self.code} - {self.name}"

class LeaveRequest(TimeStampedModel):
    STATUS_CHOICES = [("pending","Pending"),("approved","Approved"),("rejected","Rejected")]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    date_from = models.DateField()
    date_to = models.DateField()
    unit = models.CharField(max_length=8, default="day")  # day|half|hour
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    approver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_leaves")
    def __str__(self): return f"{self.employee.code} {self.leave_type.code} {self.date_from}→{self.date_to} ({self.status})"

# ====== Đăng ký/đổi ca ======
class ShiftRegistration(TimeStampedModel):
    STATUS_CHOICES = [("pending","Pending"),("approved","Approved"),("rejected","Rejected")]
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="shift_regs")
    date = models.DateField()
    slot = models.PositiveSmallIntegerField(default=1)  # 1..3
    template = models.ForeignKey(ShiftTemplate, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    reason = models.CharField(max_length=255, blank=True)
    def __str__(self): return f"{self.employee.code} {self.date} slot{self.slot} req {self.template.code} ({self.status})"

# ====== Timesheet (tổng hợp theo ca) ======
class TimesheetEntry(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="timesheet_entries")
    date = models.DateField(db_index=True)
    slot = models.PositiveSmallIntegerField(default=1)
    shift_plan = models.ForeignKey(ShiftPlan, on_delete=models.SET_NULL, null=True, blank=True)
    minutes_worked = models.PositiveIntegerField(default=0)
    minutes_late = models.PositiveIntegerField(default=0)
    minutes_early = models.PositiveIntegerField(default=0)
    minutes_ot = models.PositiveIntegerField(default=0)
    minutes_leave_paid = models.PositiveIntegerField(default=0)
    minutes_leave_unpaid = models.PositiveIntegerField(default=0)
    anomalies = models.JSONField(default=dict, blank=True)  # lưu cảnh báo
    locked = models.BooleanField(default=False)

    class Meta:
        unique_together = [("employee","date","slot")]
        indexes = [models.Index(fields=["employee","date"])]

# ====== Cài đặt & Chạy bảng lương ======
class PayrollSetting(TimeStampedModel):
    period = models.CharField(max_length=7, unique=True)  # 'YYYY-MM'
    payday = models.PositiveSmallIntegerField(default=5)  # trả lương ngày mấy hàng tháng
    std_working_days = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("26.0"))
    std_minutes_per_day = models.PositiveIntegerField(default=480)  # 8h
    ot_coeff_weekday = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.50"))
    ot_coeff_weekend = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.00"))
    ot_coeff_night = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.30"))

class PayrollRun(TimeStampedModel):
    STATUS_CHOICES = [("draft","Draft"),("calculated","Calculated"),("exported","Exported")]
    period = models.CharField(max_length=7)  # 'YYYY-MM'
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    note = models.CharField(max_length=255, blank=True)

class PayrollLine(TimeStampedModel):
    payroll = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="lines")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    base_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    ot_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    gross = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
