from erp_the20.models import Department
from django.core.exceptions import ValidationError

# tạo phòng ban
def create_department(data: dict) -> Department:
    if Department.objects.filter(code=data["code"]).exists(): # kiểm tra mã phòng ban có bị trùng không
        raise ValidationError("Department code must be unique") # nếu bị trùng thì báo lỗi
    return Department.objects.create(**data) # nếu không bị trùng thì tạo phòng ban mới

# cập nhật phòng ban
def update_department(dept: Department, data: dict) -> Department:
    if "code" in data and data["code"] != dept.code: # kiểm tra mã phòng ban có thay đổi không
        if Department.objects.filter(code=data["code"]).exists(): # kiểm tra mã phòng ban có bị trùng không
            raise ValidationError("Department code must be unique") # nếu bị trùng thì báo lỗi
        dept.code = data["code"] # nếu không bị trùng thì gán mã phòng ban mới
    if "name" in data: # kiểm tra tên phòng ban có thay đổi không
        dept.name = data["name"] # nếu có thì gán tên phòng ban mới
    dept.save() # lưu thay đổi
    return dept

# xóa phòng ban
def delete_department(dept: Department): 
    dept.delete()
    return None

# vô hiệu phòng ban
def deactivate_department(dept: Department):
    dept.is_active = False
    dept.save(update_fields=["is_active"])
    return dept

# kích hoạt phòng ban
def activate_department(dept: Department):
    dept.is_active = True
    dept.save(update_fields=["is_active"])
    return dept


