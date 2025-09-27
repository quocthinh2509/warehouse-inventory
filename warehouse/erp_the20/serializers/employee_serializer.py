from rest_framework import serializers
from erp_the20.models import Employee
from erp_the20.serializers.department_serializer import DepartmentReadSerializer
from erp_the20.serializers.position_serializer import PositionReadSerializer

class EmployeeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id", "code","user_name", "full_name", "email", "phone", "base_salary", "department","position", "is_active"]



class EmployeeReadSerializer(serializers.ModelSerializer):
    department = DepartmentReadSerializer(read_only=True)
    position = PositionReadSerializer(read_only=True)
    class Meta:
        model = Employee
        fields = ["id", "code","user_name", "full_name", "email", "phone", "department","position", "is_active"]
