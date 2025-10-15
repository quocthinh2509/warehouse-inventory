from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.db.models import Q, UniqueConstraint
from .mixins import TimeStampedModel

class ShiftTemplate(TimeStampedModel):
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=120)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.IntegerField(default=0)
    overnight = models.BooleanField(default=False)
    pay_factor = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Hệ số cho ca (ví dụ: ca đêm 1.5)"
    )

    class Meta:
        ordering = ["code"]
        db_table = "ShiftTemplate"
        constraints = [
            UniqueConstraint(fields=["code"], condition=Q(deleted_at__isnull=True), name="uniq_active_shifttemplate_code"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"
