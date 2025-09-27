from rest_framework import serializers
from erp_the20.models import Position
from erp_the20.serializers.department_serializer import DepartmentReadSerializer


class PositionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "code", "name", "department"]


#dùng để đọc thôi
class PositionReadSerializer(serializers.ModelSerializer):
    department = DepartmentReadSerializer(read_only=True)
    class Meta:
        model = Position
        fields = ["id", "code", "name","department"]
        read_only_fields = ["id", "code", "name", "epartment"]
