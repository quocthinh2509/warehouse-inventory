from erp_the20.models import Employee, Department, Position, Worksite

# lấy nhân viên theo id
def get_employee_by_id(emp_id: int):
    return Employee.objects.filter(id=emp_id).first()

# lấy tất cả nhân viên
def list_all_employees():
    return Employee.objects.all().select_related("department", "position", "default_worksite").order_by("full_name")

# lấy tất cả nhân viên đang hoạt động
def list_active_employees():
    return Employee.objects.filter(is_active=True).select_related("department", "position", "default_worksite").order_by("full_name")