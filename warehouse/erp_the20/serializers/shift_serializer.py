# erp_the20/serializers/shift_serializer.py
from datetime import datetime
from rest_framework import serializers
from erp_the20.models import ShiftTemplate, ShiftInstance, ShiftRegistration, ShiftAssignment
from erp_the20.serializers.employee_serializer import EmployeeReadSerializer

# ---------- Write serializers ----------
class ShiftTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = "__all__"

class ShiftInstanceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftInstance
        fields = "__all__"

class ShiftRegistrationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftRegistration
        fields = "__all__"

class ShiftAssignmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftAssignment
        fields = "__all__"

# ---------- Read serializers ----------
class ShiftTemplateReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = [
            "id", "code", "name", "start_time", "end_time",
            "break_minutes", "overnight"
        ]

class ShiftInstanceReadSerializer(serializers.ModelSerializer):
    # Map tên output "shift_template" -> field thật "template"
    template = ShiftTemplateReadSerializer( read_only=True)
    class Meta:
        model = ShiftInstance
        fields = ["id", "date", "template", "status"]

class ShiftRegistrationReadSerializer(serializers.ModelSerializer):
    employee = EmployeeReadSerializer(read_only=True)
    shift_instance = ShiftInstanceReadSerializer(read_only=True)
    class Meta:
        model = ShiftRegistration
        fields = ["id", "employee", "shift_instance", "created_by", "status", "reason"]

class ShiftAssignmentReadSerializer(serializers.ModelSerializer):
    employee = EmployeeReadSerializer(read_only=True)
    shift_instance = ShiftInstanceReadSerializer(read_only=True)
    class Meta:
        model = ShiftAssignment
        fields = ["id", "employee", "shift_instance", "assigned_by", "status"]



class ShiftInstanceQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to   = serializers.DateField(required=False)

    def validate(self, attrs):
        df = attrs.get("date_from")
        dt = attrs.get("date_to")
        if df and dt and df > dt:
            raise serializers.ValidationError({"date_to": "date_to must be >= date_from"})
        return attrs
