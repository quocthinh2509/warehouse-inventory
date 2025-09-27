from erp_the20.models import Position
from django.core.exceptions import ValidationError

# ----------------------
# Position Service
# ----------------------

def create_position(data: dict) -> Position:
    """
    Tạo Position mới
    
    Args:
        data (dict): {"code": str, "name": str, "default_department": Department}
        
    Raises:
        ValidationError: nếu code bị trùng
        
    Returns:
        Position: object mới tạo
    """
    if Position.objects.filter(code=data["code"]).exists():
        raise ValidationError("Position code must be unique")
    return Position.objects.create(**data)


def update_position(pos: Position, data: dict) -> Position:
    """
    Cập nhật Position
    
    Args:
        pos (Position): object cần update
        data (dict): fields cần update {"code", "name", "default_department"}
        
    Raises:
        ValidationError: nếu code mới bị trùng
        
    Returns:
        Position: object đã update
    """
    if "code" in data and data["code"] != pos.code:
        if Position.objects.filter(code=data["code"]).exclude(id=pos.id).exists():
            raise ValidationError("Position code must be unique")
        pos.code = data["code"]

    if "name" in data:
        pos.name = data["name"]

    if "default_department" in data:
        pos.default_department = data["default_department"]

    pos.save()
    return pos


def delete_position(pos: Position) -> None:
    """
    Xóa Position.
    
    Args:
        pos (Position): object cần xóa
        
    Returns:
        None
    """
    pos.delete()
