from django.db import models
from .hr import Employee, Worksite, Shift, TimeStampedModel

class AttendanceRecord(TimeStampedModel):
    METHOD_CHOICES = (('web','Web'),('mobile','Mobile'),('lark','Lark'),('api','API'))
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    worksite = models.ForeignKey(Worksite, on_delete=models.PROTECT)
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    check_in_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default='web')
    accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    note_user = models.CharField(max_length=255, blank=True)
    is_valid = models.BooleanField(default=True)
    invalid_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['employee','check_in_at']),
            models.Index(fields=['employee','check_out_at']),
        ]
