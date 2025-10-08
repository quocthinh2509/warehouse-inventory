from typing import Optional
from django.db.models import QuerySet, Q
from erp_the20.models import ShiftTemplate

# lấy QuerySet cơ bản, trả về các bảng ghi deleted_at là null 
def base_qs(include_deleted: bool = False) -> QuerySet[ShiftTemplate]:
    qs = ShiftTemplate.objects.all()
    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)
    return qs

# Lấy 1 ShiftTemplate theo PK
def get_by_id(pk: int, include_deleted: bool = False) -> Optional[ShiftTemplate]:
    return base_qs(include_deleted).filter(pk=pk).first()

# Lấy 1 ShiftTemplate theo code
def get_by_code(code: str, include_deleted: bool = False) -> Optional[ShiftTemplate]:
    return base_qs(include_deleted).filter(code=code).first()

# Lấy danh sách ShiftTemplate, hỗ trợ filter và sắp xếp
def list_shift_templates(
    q: Optional[str] = None,
    overnight: Optional[bool] = None,
    ordering: Optional[str] = None,
    include_deleted: bool = False,
) -> QuerySet[ShiftTemplate]:
    qs = base_qs(include_deleted)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    if overnight is not None:
        qs = qs.filter(overnight=overnight)
    if ordering:
        qs = qs.order_by(ordering)
    return qs

# Lấy danh sách ShiftTemplate theo trình tự của start_time 
def list_all_ordered_by_start_time(include_deleted: bool = False) -> QuerySet[ShiftTemplate]:
    return base_qs(include_deleted).order_by("start_time")
