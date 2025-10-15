from typing import Optional
from erp_the20.models import EmployeeProfile

def profile_by_user(user_id: int) -> Optional[EmployeeProfile]:
    return EmployeeProfile.objects.filter(user_id=user_id).first()
