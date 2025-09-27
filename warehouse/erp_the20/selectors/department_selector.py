from erp_the20.models import Department

# Lấy Department theo ID
def get_department_by_id(dept_id: int):
    """
    Trả về Department theo ID.
    """
    return Department.objects.filter(id=dept_id).first()

# Lấy Department theo code
def get_department_by_code(code: str):
    """
    Trả về Department theo code.
    """
    return Department.objects.filter(code=code).first()

# Lấy danh sách tất cả Department
def list_all_departments():
    """
    Trả về danh sách tất cả Department, sắp xếp theo name.
    """
    return Department.objects.all().order_by("name")
