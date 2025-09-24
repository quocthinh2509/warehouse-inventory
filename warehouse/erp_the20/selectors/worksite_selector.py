from erp_the20.models import Worksite

# lấy địa điểm làm việc theo id
def get_worksite_by_id(worksite_id: int):
    return Worksite.objects.filter(id=worksite_id).first()

# lấy tất cả địa điểm làm việc
def list_all_worksites():
    return Worksite.objects.all().order_by("id")

# lấy tất cả địa điểm làm việc đang hoạt động
def list_active_worksites():
    return Worksite.objects.filter(is_active=True).order_by("id")
