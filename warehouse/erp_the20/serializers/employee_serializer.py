from rest_framework import serializers
from erp_the20.models import Employee
from erp_the20.serializers.department_serializer import DepartmentReadSerializer
from erp_the20.serializers.position_serializer import PositionReadSerializer
from erp_the20.serializers.worksite_serializer import WorksiteReadSerializer

class EmployeeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id", "code", "full_name", "email", "phone", "base_salary", "department","position", "default_worksite", "is_active"]



class EmployeeReadSerializer(serializers.ModelSerializer):
    department = DepartmentReadSerializer(read_only=True)
    position = PositionReadSerializer(read_only=True)
    default_worksite = WorksiteReadSerializer(read_only=True)
    class Meta:
        model = Employee
        fields = ["id", "code", "full_name", "email", "phone", "base_salary", "department","position", "default_worksite", "is_active"]
