from erp_the20.models import Department

#lấy phòng ban theo id
def get_department_by_id(dept_id: int):
    return Department.objects.filter(id=dept_id).first()

#lấy tất cả phòng ban
def list_all_departments():
    return Department.objects.filter().order_by("id")

#lấy tất cả phòng ban đang hoạt động
def list_active_departments():
    return Department.objects.filter(is_active=True).order_by("id")