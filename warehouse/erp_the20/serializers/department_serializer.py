from rest_framework import serializers
from erp_the20.models import Department

class DepartmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]

#dùng để đọc thôi
class DepartmentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]
