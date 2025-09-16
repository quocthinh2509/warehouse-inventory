from django.db import models
from decimal import Decimal
from .hr import TimeStampedModel, Employee

class PayrollPeriod(TimeStampedModel):
    code = models.CharField(max_length=32, unique=True)  # e.g. 2025-09
    start_date = models.DateField()
    end_date = models.DateField()
    locked = models.BooleanField(default=False)
    def __str__(self): return self.code

class PayrollLine(TimeStampedModel):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='lines')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    days_worked = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    leave_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    bonuses = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))