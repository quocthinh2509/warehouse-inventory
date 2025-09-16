from django.db import models
from django.conf import settings
from decimal import Decimal

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class StatusMixin(models.Model):
    STATUS_CHOICES = (
        ('active','Active'), ('inactive','Inactive'), ('archived','Archived')
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active')
    class Meta:
        abstract = True

class Department(TimeStampedModel, StatusMixin):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    def __str__(self): return f"{self.code} - {self.name}"

class Worksite(TimeStampedModel, StatusMixin):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radius_m = models.PositiveIntegerField(default=150)
    def __str__(self): return f"{self.code} - {self.name}"

class Shift(TimeStampedModel, StatusMixin):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.PositiveIntegerField(default=0)
    def __str__(self): return f"{self.code} {self.name} {self.start_time}-{self.end_time}"

class Employee(TimeStampedModel, StatusMixin):
    code = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    default_shift = models.ForeignKey(Shift, null=True, blank=True, on_delete=models.SET_NULL)
    default_worksite = models.ForeignKey(Worksite, null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)
    def __str__(self): return f"{self.code} - {self.full_name}"

class LeaveType(TimeStampedModel, StatusMixin):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    paid = models.BooleanField(default=True)
    def __str__(self): return self.name

class LeaveRequest(TimeStampedModel, StatusMixin):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=(
        ('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('rejected','Rejected')
    ), default='submitted')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_leaves')

    class Meta:
        ordering = ['-start_date','-id']