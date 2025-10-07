
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db.models import Q, CheckConstraint  


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
    # có thể để hệ số ở chổ này ( theo từng ngày nhưng default là 1, những ngày lễ có thể gắn là 2 hoặc 1,5 )

    class Meta:
        unique_together = [("template", "date")]
        ordering = ["-date", "template_id"]


# ===== Attendance =====
class AttendanceEvent(TimeStampedModel): # một ca làm ( thực tế )
    SOURCE_CHOICES = [
        ("web", "Web"),
        ("mobile", "Mobile"),
        ("lark", "Lark"),
        ("googleforms", "Google Forms"),
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

# models.py (đoạn LeaveRequest tối giản)
class LeaveRequest(TimeStampedModel):
    """
    Đơn nghỉ phép tối giản:
    - Người gửi đơn chính là employee_id
    - Mọi quyết định (approved/rejected/cancelled) dùng 1 field decided_by
    """
    LEAVE_REQUEST_STATUS = [
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    paid = models.BooleanField(default=False) # chổ này để tính xem là có trả tiền hay không.

    employee_id = models.IntegerField(null=True, blank=True)

    # Ngày bắt đầu và kết thúc nghỉ (theo ngày)
    start_date = models.DateField()
    end_date   = models.DateField()

    # Nếu xin theo giờ (optional). Nếu dùng theo ngày thì để trống.
    hours  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True)

    status = models.CharField(max_length=16, choices=LEAVE_REQUEST_STATUS, default="submitted")

    # Thời điểm có quyết định (duyệt/từ chối/huỷ)
    decision_ts = models.DateTimeField(null=True, blank=True)

    # Người ra quyết định (approve/reject/cancel)
    decided_by = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee_id", "start_date", "end_date", "status"]),
        ]
        constraints = [
            CheckConstraint(
                name="leave_dates_valid",
                check=Q(end_date__gte=models.F("start_date")),
            ),
        ]

    def __str__(self):
        return f"LV {self.employee_id} {self.leave_type} {self.start_date}→{self.end_date} [{self.status}]"

class AttendanceSummary(TimeStampedModel):
    ATTENDANCE_STATUS = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("late", "Late"),
        ("early_leave", "Early Leave"),
        ("working_remotely", "Working Remotely"),
    ]



    # khóa ngày  - nhân viên ( 1 dòng / nhân viên / ngày )
    employee_id = models.IntegerField(null=True, blank=True)  # thay vì FK Employee
    date = models.DateField() 

    # phút kế hoạch và thực tế 
    planned_minutes = models.IntegerField(default=0) # phút kế hoạch
    worked_minutes = models.IntegerField(default=0)  # giờ làm thực tế
    late_minutes = models.IntegerField(default=0)    # phút trễ
    early_leave_minutes = models.IntegerField(default=0)  # phút về sớm
    overtime_minutes = models.IntegerField(default=0)  # làm thêm 


    on_leave = models.ForeignKey(LeaveRequest,  null=True, blank=True, on_delete=models.SET_NULL)

    status = models.CharField(max_length=16,choices=ATTENDANCE_STATUS, default="absent")  
    notes = models.TextField(blank=True) 

    # 1) Snapshot toàn bộ event trong ngày (đã lọc theo ngày & is_valid)
    #    Mỗi item nên lưu: {id, ts, event_type, source, is_valid}
    events = models.JSONField(default=list)

    # 2) Các cặp in/out đã ghép
    #    Ví dụ: [{"in": "...", "out": "...", "source_in": "mobile", "source_out": "web",
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


# class event V2

class AttendanceSummaryV2(TimeStampedModel):
    # mỗi nhân viên sẽ có một summary tạo sẵn, chỉ cần vào update thôi, nếu có nhiều ca thì tạo nhiều summary
    SOURCE_CHOICES = [
        ("web", "Web"),
        ("mobile", "Mobile"),
        ("lark", "Lark"),
        ("googleforms", "Google Forms"),
    ]
    WORK_MODE = [
        ("onsite", "Onsite (Văn phòng)"),
        ("remote", "Remote (Online)"),
    ]

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELED = "canceled", "Canceled"
    
    # gắn với employee
    employee_id = models.IntegerField(null=True, blank=True)# thay vì FK Employee
    shift_instance = models.ForeignKey(ShiftInstance, null=False, blank=False, on_delete=models.PROTECT) 
    on_leave = models.ForeignKey(LeaveRequest, null=True,blank=True,on_delete=models.SET_NULL)
    
    # thời gian ra vào ca 
    ts_in = models.DateTimeField(null=True, blank=True) #
    ts_out =  models.DateTimeField(null=True, blank=True)


    # nguồn dữ liệu đến từ
    source = models.CharField(max_length=16,choices = SOURCE_CHOICES, default="web")  
    # loại hình làm việc ( để tính hệ số lương)
    work_mode = models.CharField(max_length=16,choices = WORK_MODE, default="onsite")

    bonus = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Tiền thưởng/bonus cho phiên làm việc (nếu có)."
    ) # hệ số của ca làm 
    
    

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    is_valid = models.BooleanField(default=False)  #chỉ true khi đã duyệt

    requested_by = models.IntegerField(null=True, blank=True)
    requested_at = models.DateTimeField(default=timezone.now, editable=False)

    approved_by = models.IntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=255, blank=True, default="")

    raw_payload = models.JSONField(null=True, blank=True) 
    class Meta:
        ordering = ["shift_instance__date","ts_in"]
        constraints =[
            CheckConstraint(
                name="approved_requires_is_valid_true",
                check=Q(status="approved", is_valid=True) | ~Q(status="approved")
            ),
        ]
        indexes = [
            models.Index(fields=["employee_id", "status"]),
            models.Index(fields=["status", "is_valid"]),
        ]


    @property
    def date(self):
        return self.shift_instance.date if self.shift_instance_id else None

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



    

