# erp_the20/repositories/profile_repository.py
from typing import Optional, Tuple, List
from django.db.models import Q
from erp_the20.models import EmployeeProfile

def get(user_id: int) -> Optional[EmployeeProfile]:
    return EmployeeProfile.objects.filter(user_id=user_id).first()

def get_or_create(user_id: int) -> EmployeeProfile:
    obj, _ = EmployeeProfile.objects.get_or_create(user_id=user_id)
    return obj

def save_profile(user_id: int, **fields) -> EmployeeProfile:
    obj = get_or_create(user_id)
    for k, v in fields.items():
        setattr(obj, k, v)
    obj.save()
    return obj

def list_profiles(q: Optional[str] = None, limit: int = 50, offset: int = 0) -> Tuple[int, List[EmployeeProfile]]:
    qs = EmployeeProfile.objects.all().order_by("-updated_at")
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q) |
            Q(cccd__icontains=q)
        )
    total = qs.count()
    items = list(qs[offset:offset+limit])
    return total, items
