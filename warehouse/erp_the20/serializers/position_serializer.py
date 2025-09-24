from rest_framework import serializers
from erp_the20.models import Position
from erp_the20.serializers.department_serializer import DepartmentReadSerializer


class PositionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "code", "name", "default_department"]


#dùng để đọc thôi
class PositionReadSerializer(serializers.ModelSerializer):
    default_department = DepartmentReadSerializer(read_only=True)
    class Meta:
        model = Position
        fields = ["id", "code", "name","default_department"]
        read_only_fields = ["id", "code", "name", "default_department"]
