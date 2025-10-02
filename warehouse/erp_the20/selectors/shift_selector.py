from django.db.models import Q, F
from erp_the20.models import (
    ShiftTemplate,
    ShiftInstance,
)
from datetime import date, datetime, timedelta


# ============================================================
#  SHIFT TEMPLATE
# ============================================================

def get_shift_template(template_id: int) -> ShiftTemplate | None:
    """Lấy 1 ShiftTemplate theo id."""
    return ShiftTemplate.objects.filter(id=template_id).first()


def list_shift_templates() -> list[ShiftTemplate]:
    """Lấy toàn bộ ShiftTemplate."""
    return ShiftTemplate.objects.all()


# ============================================================
#  SHIFT INSTANCE
# ============================================================

def get_shift_instance(instance_id: int) -> ShiftInstance | None:
    """Lấy 1 ShiftInstance theo id."""
    return ShiftInstance.objects.filter(id=instance_id).first()


def list_shift_instances(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> list[ShiftInstance]:
    """
    Lấy danh sách ShiftInstance, có filter theo ngày và status.
    """
    qs = ShiftInstance.objects.select_related("template").all()

    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if status:
        qs = qs.filter(status=status)

    return qs




def instances_around(ts) -> list[ShiftInstance]:
    """Lấy các ShiftInstance có thể bao quanh timestamp `ts`."""
    return (
        ShiftInstance.objects.filter(
            Q(date=ts.date())
            | Q(
                date=ts.date() - timedelta(days=1),
                template__end_time__gt=F("template__start_time"),
            )
            | Q(
                date=ts.date() + timedelta(days=1),
                template__end_time__lt=F("template__start_time"),
            )
        )
        .select_related("template")
        .all()
    )


def planned_minutes(inst: ShiftInstance) -> int:
    """Tính tổng phút làm việc thực tế trong ca (đã trừ break)."""
    start_dt = datetime.combine(date.min, inst.template.start_time)
    end_dt = datetime.combine(date.min, inst.template.end_time)
    if inst.template.overnight and end_dt <= start_dt:
        end_dt += timedelta(days=1)
    total_minutes = int((end_dt - start_dt).total_seconds() // 60) - inst.template.break_minutes
    return max(total_minutes, 0)

# lấy các shift instance trong ngày hôm nay (theo múi giờ UTC+7)
def list_today_shift_instances() -> list[ShiftInstance]:
    """Lấy các ShiftInstance trong ngày hôm nay (theo múi giờ UTC+7)."""
    utc_now = datetime.utcnow()
    vn_now = utc_now + timedelta(hours=7)
    today = vn_now.date()
    qs = ShiftInstance.objects.select_related("template").filter(date=today)
    return list(qs)