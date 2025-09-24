from rest_framework import serializers
from erp_the20.models import Worksite

class WorksiteWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worksite
        fields = ["id", "code", "name", "address", "lat", "lng", "radius_m", "is_active"]

#dùng để đọc thôi
class WorksiteReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worksite
        fields = ["id", "code", "name", "address"]
        read_only_fields = ["id", "code", "name", "address"]
