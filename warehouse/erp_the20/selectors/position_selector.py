from erp_the20.models import Position

#lấy vị trí theo id
def get_position_by_id(position_id: int):
    return Position.objects.filter(id=position_id).first()

#lấy tất cả vị trí
def list_all_positions():
    return Position.objects.all().select_related("default_department").order_by("id")



