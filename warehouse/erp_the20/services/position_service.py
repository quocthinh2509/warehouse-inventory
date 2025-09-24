from erp_the20.models import Position
from django.core.exceptions import ValidationError

def create_position(data: dict) -> Position:
    if Position.objects.filter(code=data["code"]).exists():
        raise ValidationError("Position code must be unique")
    return Position.objects.create(**data)

def update_position(pos: Position, data: dict) -> Position:
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

def delete_position(pos: Position):
    pos.delete()
    return None

