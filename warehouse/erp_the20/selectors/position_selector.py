from erp_the20.models import Position

# Lấy Position theo ID
def get_position_by_id(pos_id: int):
    """
    Trả về Position theo ID.
    """
    return Position.objects.filter(id=pos_id).first()

# Lấy Position theo code
def get_position_by_code(code: str):
    """
    Trả về Position theo code.
    """
    return Position.objects.filter(code=code).first()

# Lấy danh sách tất cả Position
def list_all_positions():
    """
    Trả về danh sách tất cả Position, kèm department, sắp xếp theo name.
    """
    return Position.objects.all().select_related("department").order_by("name")
