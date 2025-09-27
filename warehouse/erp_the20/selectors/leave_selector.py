from erp_the20.models import LeaveType

# Lấy LeaveType theo ID
def get_leave_type_by_id(leave_type_id: int):
    """
    Trả về LeaveType theo ID.
    """
    return LeaveType.objects.filter(id=leave_type_id).first()

# Lấy LeaveType theo code
def get_leave_type_by_code(code: str):
    """
    Trả về LeaveType theo code.
    """
    return LeaveType.objects.filter(code=code).first()

# Lấy danh sách tất cả LeaveType
def list_all_leave_types():
    """
    Trả về danh sách tất cả LeaveType, sắp xếp theo code.
    """
    return LeaveType.objects.all().order_by("code")
