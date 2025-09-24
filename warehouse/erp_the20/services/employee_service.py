from erp_the20.models import Employee
from django.core.exceptions import ValidationError




def create_employee(data: dict) -> Employee:
    if Employee.objects.filter(code=data["code"]).exists():
        raise ValidationError("Employee code must be unique")
    if Employee.objects.filter(email=data["email"]).exists():
        raise ValidationError("Employee email must be unique")
    return Employee.objects.create(**data)

def deactivate_employee(emp: Employee):
    emp.is_active = False
    emp.save(update_fields=["is_active"])
    return emp

def activate_employee(emp: Employee):
    emp.is_active = True
    emp.save(update_fields=["is_active"])
    return emp

def update_employee(emp: Employee, data: dict) -> Employee:
    if "code" in data and data["code"] != emp.code:
        if Employee.objects.filter(code=data["code"]).exists():
            raise ValidationError("Employee code must be unique")
        emp.code = data["code"]
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
    if "default_worksite" in data:
        emp.default_worksite = data["default_worksite"]
    if "is_active" in data:
        emp.is_active = data["is_active"]
    emp.save()
    return emp

def delete_employee(emp: Employee):
    emp.delete()
    return None

