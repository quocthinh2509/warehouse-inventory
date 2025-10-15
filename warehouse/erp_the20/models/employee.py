from django.db import models
from .mixins import TimeStampedModel

class EmployeeProfile(TimeStampedModel):
    user_id = models.IntegerField(unique=True, db_index=True)
    full_name = models.CharField(max_length=200, blank=True, default="")
    cccd = models.CharField(max_length=20, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=300, blank=True, default="")
    first_day_in_job = models.DateField(null=True, blank=True)
    email = models.CharField(max_length=254, blank=True, default="")
    doc_link = models.CharField(max_length=300, blank=True, default="")
    picture_link = models.CharField(max_length=300, blank=True, default="")
    offer_content = models.TextField(blank=True, default="")
    salary = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    degree = models.CharField(max_length=120, blank=True, default="")
    old_company = models.CharField(max_length=200, blank=True, default="")
    tax_code = models.CharField(max_length=32, blank=True, default="")
    bhxh = models.CharField(max_length=32, blank=True, default="")
    car = models.CharField(max_length=200, blank=True, default="", help_text="Loại xe, số xe, năm SX")
    temporary_address = models.CharField(max_length=300, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    emergency_contact = models.CharField(max_length=200, blank=True, default="")
    emergency_phone = models.CharField(max_length=32, blank=True, default="")
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "EmployeeProfile"
