
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
    department = models.ForeignKey(Department, on_delete=models.SET_NULL,null=True,blank=True) 
    class Meta:
        ordering = ["name"]

    def __str__(self): return self.name


# ===== Shifts & Scheduling ===== mẫu ca làm
class ShiftTemplate(TimeStampedModel):   
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    start_time = models.TimeField() 
    end_time = models.TimeField() 
    break_minutes = models.IntegerField(default=0) 
    overnight = models.BooleanField(default=False) 

    class Meta:
        ordering = ["code"]

    def __str__(self): return f"{self.code} - {self.name}"


class ShiftInstance(TimeStampedModel):  # ca làm việc cụ thể theo ngày
    SHIFT_STATUS = [ 
        ("planned", "Planned"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    template = models.ForeignKey(ShiftTemplate, on_delete=models.PROTECT) 
    date = models.DateField()
    status = models.CharField(choices=SHIFT_STATUS, max_length=16, default="planned") 

    class Meta:
        unique_together = [("template", "date")]
        ordering = ["-date", "template_id"]


# ===== Attendance =====
class AttendanceEvent(TimeStampedModel):
    SOURCE_CHOICES = [
        ("web", "Web"),
        ("mobile", "Mobile"),
        ("lark", "Lark"),
        ("googlefroms", "Google Forms"),
    ]
    EVENT_TYPES = (("in", "in"), ("out", "out"))

    employee_id = models.IntegerField(null=True, blank=True)# thay vì FK Employee
    shift_instance = models.ForeignKey(ShiftInstance, null=True, blank=True, on_delete=models.SET_NULL) 
    event_type = models.CharField(max_length=16, choices=EVENT_TYPES) 
    ts = models.DateTimeField() 
    source = models.CharField(max_length=16,choices = SOURCE_CHOICES, default="web")  
    is_valid = models.BooleanField(default=True) 
    raw_payload = models.JSONField(null=True, blank=True) 

    class Meta:
        ordering = ["-ts"]


class AttendanceSummary(TimeStampedModel):
    ATTENDANCE_STATUS = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("late", "Late"),
        ("early_leave", "Early Leave"),
        ("working_remotely", "Working Remotely"),
    ]

    employee_id = models.IntegerField(null=True, blank=True)  # thay vì FK Employee
    date = models.DateField() 
    planned_minutes = models.IntegerField(default=0) 
    worked_minutes = models.IntegerField(default=0) 
    late_minutes = models.IntegerField(default=0) 
    early_leave_minutes = models.IntegerField(default=0) 
    overtime_minutes = models.IntegerField(default=0) 
    status = models.CharField(max_length=16,choices=ATTENDANCE_STATUS, default="absent")  
    notes = models.TextField(blank=True) 
    segments = models.JSONField(default=list) 

    class Meta:
        ordering = ["-date"]


class AttendanceCorrection(TimeStampedModel):
    CORRECTION_STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    employee_id = models.IntegerField(null=True, blank=True) # thay vì FK Employee
    date = models.DateField() 
    type = models.CharField(max_length=32)  
   
    status = models.CharField(max_length=16, default="pending", choices = CORRECTION_STATUS)  
   
    changeset = models.JSONField() 

    class Meta:
        ordering = ["-created_at"]


# ===== Leave =====
class LeaveType(TimeStampedModel): 
    code = models.CharField(max_length=16, unique=True) 
    name = models.CharField(max_length=120) 
    paid = models.BooleanField(default=True) 
    annual_quota_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00")) 
    class Meta:
        ordering = ["code"]

    def __str__(self): return f"{self.code} - {self.name}"


class LeaveBalance(TimeStampedModel): 
    employee_id = models.IntegerField(null=True, blank=True)  # thay vì FK Employee
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT) 
    period = models.IntegerField()  
    opening = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00")) 
    accrued = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00")) 
    used = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00")) 

    class Meta:
        ordering = ["-period"]


class LeaveRequest(TimeStampedModel): 
    LEAVE_REQUEST_STATUS = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    employee_id = models.IntegerField(null=True, blank=True)  # thay vì FK Employee
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField() 
    end_date = models.DateField() 
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) 
    reason = models.TextField(blank=True)  
    status = models.CharField(max_length=16, default="draft",choices = LEAVE_REQUEST_STATUS)  
    decision_ts = models.DateTimeField(null=True, blank=True) 

    class Meta:
        ordering = ["-created_at"]


# ===== Settings / Audit / Notifications =====
class HolidayCalendar(TimeStampedModel): 
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["-date"]


class ApprovalFlow(TimeStampedModel): 
    object_type = models.CharField(max_length=32)  
    role = models.CharField(max_length=32)        
    step = models.IntegerField(default=1)

    class Meta:
        unique_together = [("object_type", "role", "step")]
        ordering = ["object_type", "step"]


class Notification(TimeStampedModel): 
    to_user = models.IntegerField(null=True, blank=True)  # thay vì FK Employee
    channel = models.CharField(max_length=16, default="inapp")  
    title = models.CharField(max_length=200)
    body = models.TextField()
    payload = models.JSONField(null=True, blank=True)
    delivered = models.BooleanField(default=False)


class AuditLog(TimeStampedModel): 
    actor = models.IntegerField(null=True, blank=True)  # thay vì FK Employee
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
