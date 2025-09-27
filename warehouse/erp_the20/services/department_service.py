from erp_the20.models import Department
from django.core.exceptions import ValidationError

# ----------------------
# Department Service
# ----------------------

def create_department(data: dict) -> Department:
    """
    Tạo mới một Department.
    
    Args:
        data (dict): {"code": str, "name": str}
        
    Raises:
        ValidationError: nếu code bị trùng
        
    Returns:
        Department: object mới tạo
    """
    if Department.objects.filter(code=data["code"]).exists():
        raise ValidationError("Department code must be unique")
    return Department.objects.create(**data)


def update_department(dept: Department, data: dict) -> Department:
    """
    Cập nhật thông tin Department.
    
    Args:
        dept (Department): object cần update
        data (dict): fields cần update {"code": str, "name": str}
        
    Raises:
        ValidationError: nếu code mới bị trùng
        
    Returns:
        Department: object đã update
    """
    if "code" in data and data["code"] != dept.code:
        if Department.objects.filter(code=data["code"]).exists():
            raise ValidationError("Department code must be unique")
        dept.code = data["code"]

    if "name" in data:
        dept.name = data["name"]

    dept.save()
    return dept


def delete_department(dept: Department) -> None:
    """
    Xóa Department.
    
    Args:
        dept (Department): object cần xóa
        
    Returns:
        None
    """
    dept.delete()
