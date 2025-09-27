from erp_the20.models import Employee
from django.db.models import Q
# Lấy nhân viên theo ID
def get_employee_by_id(emp_id: int):
    """
    Trả về Employee theo ID.
    """
    return Employee.objects.filter(id=emp_id).first()

# Lấy nhân viên theo code
def get_employee_by_code(code: str):
    """
    Trả về Employee theo code.
    """
    return Employee.objects.filter(code=code).first()

def get_employee_by_user_name(user_name: str):
    """
    Trả về Employee theo đúng user_name (chính xác, không phân biệt hoa thường).
    """
    if not user_name:
        return None
    # strip để tránh space và dùng icontains hoặc iexact nếu muốn case-insensitive
    return Employee.objects.filter(
        Q(user_name__iexact=str(user_name).strip()),  # so sánh không phân biệt hoa thường
        is_active=True
    ).first()
# Lấy tất cả nhân viên
def list_all_employees():
    """
    Trả về danh sách tất cả Employee, kèm department và position, sắp xếp theo full_name.
    """
    return Employee.objects.all().select_related("department", "position").order_by("full_name")

# Lấy tất cả nhân viên đang hoạt động
def list_active_employees():
    """
    Trả về danh sách Employee đang active, kèm department và position.
    """
    return Employee.objects.filter(is_active=True).select_related("department", "position").order_by("full_name")
