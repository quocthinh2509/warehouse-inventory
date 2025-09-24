from erp_the20.models import Worksite
from django.core.exceptions import ValidationError

def create_worksite(data: dict) -> Worksite:
    if Worksite.objects.filter(code=data["code"]).exists():
        raise ValidationError("Worksite code must be unique")
    return Worksite.objects.create(**data)

def deactivate_worksite(worksite: Worksite):
    worksite.is_active = False
    worksite.save(update_fields=["is_active"])
    return worksite

def update_worksite(worksite: Worksite, data: dict) -> Worksite:
    if "code" in data and data["code"] != worksite.code:
        if Worksite.objects.filter(code=data["code"]).exists():
            raise ValidationError("Worksite code must be unique")
        worksite.code = data["code"]
    if "name" in data:
        worksite.name = data["name"]
    if "address" in data:
        worksite.address = data["address"]
    if "lat" in data:
        worksite.lat = data["lat"]
    if "lng" in data:
        worksite.lng = data["lng"]
    if "radius_m" in data:
        worksite.radius_m = data["radius_m"]
    worksite.save()
    return worksite

def activate_worksite(worksite: Worksite):
    worksite.is_active = True
    worksite.save(update_fields=["is_active"])
    return worksite

def delete_worksite(worksite: Worksite):
    worksite.delete()
    return None


