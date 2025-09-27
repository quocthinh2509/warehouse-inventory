from erp_the20.models import Employee
from django.core.exceptions import ValidationError

# ----------------------
# Employee Service
# ----------------------

def create_employee(data: dict) -> Employee:
    """
    Tạo nhân viên mới
    
    Args:
        data (dict): {"code", "full_name", "email", "phone", "department", "position"}
        
    Raises:
        ValidationError: nếu code/email bị trùng
        
    Returns:
        Employee: object mới tạo
    """
    if Employee.objects.filter(code=data["code"]).exists():
        raise ValidationError("Employee code must be unique")
    if data.get("email") and Employee.objects.filter(email=data["email"]).exists():
        raise ValidationError("Employee email must be unique")
    if data.get("user_name") and Employee.objects.filter(user_name=data["user_name"]).exists():
        raise ValidationError("Employee user name must be unique")
    return Employee.objects.create(**data)


def update_employee(emp: Employee, data: dict) -> Employee:
    """
    Cập nhật thông tin nhân viên
    
    Args:
        emp (Employee): object cần update
        data (dict): fields cần update
        
    Raises:
        ValidationError: nếu code/email mới trùng
        
    Returns:
        Employee: object đã update
    """
    if "code" in data and data["code"] != emp.code:
        if Employee.objects.filter(code=data["code"]).exists():
            raise ValidationError("Employee code must be unique")
        emp.code = data["code"]
    if "user_name" in data and data["user_name"] != emp.code:
        if Employee.objects.filter(user_name=data["user_name"]).exists():
            raise ValidationError("Employee user name must be unique")
        emp.user_name = data["user_name"]

    if "full_name" in data:
        emp.full_name = data["full_name"]

    if "email" in data and data["email"] != emp.email:
        if Employee.objects.filter(email=data["email"]).exists():
            raise ValidationError("Employee email must be unique")
        emp.email = data["email"]

    if "phone" in data:
        emp.phone = data["phone"]

    if "department" in data:
        emp.department = data["department"]

    if "position" in data:
        emp.position = data["position"]

    if "is_active" in data:
        emp.is_active = data["is_active"]

    emp.save()
    return emp


def activate_employee(emp: Employee) -> Employee:
    """
    Kích hoạt nhân viên
    
    Args:
        emp (Employee)
        
    Returns:
        Employee: object đã active
    """
    emp.is_active = True
    emp.save(update_fields=["is_active"])
    return emp


def deactivate_employee(emp: Employee) -> Employee:
    """
    Vô hiệu hóa nhân viên
    
    Args:
        emp (Employee)
        
    Returns:
        Employee: object đã inactive
    """
    emp.is_active = False
    emp.save(update_fields=["is_active"])
    return emp


def delete_employee(emp: Employee) -> None:
    """
    Xóa nhân viên
    
    Args:
        emp (Employee)
        
    Returns:
        None
    """
    emp.delete()
