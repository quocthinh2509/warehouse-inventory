# erp_the20/serializers/shift_serializer.py
from datetime import datetime
from rest_framework import serializers
from erp_the20.models import ShiftTemplate, ShiftInstance, ShiftRegistration, ShiftAssignment
from erp_the20.serializers.worksite_serializer import WorksiteReadSerializer
from erp_the20.serializers.employee_serializer import EmployeeReadSerializer

# ---------- Write serializers ----------
class ShiftTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = "__all__"

class ShiftInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftInstance
        fields = "__all__"

class ShiftRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftRegistration
        fields = ["id", "employee", "shift_instance", "status", "reason", "created_at"]
        read_only_fields = ["status", "created_at"]

class ShiftAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftAssignment
        fields = "__all__"

# ---------- Read serializers ----------
class ShiftTemplateReadSerializer(serializers.ModelSerializer):
    default_worksite = WorksiteReadSerializer(read_only=True)
    class Meta:
        model = ShiftTemplate
        fields = [
            "id", "code", "name", "start_time", "end_time",
            "break_minutes", "overnight", "weekly_days", "default_worksite"
        ]

class ShiftInstanceReadSerializer(serializers.ModelSerializer):
    # Map tên output "shift_template" -> field thật "template"
    shift_template = ShiftTemplateReadSerializer(source="template", read_only=True)
    worksite = WorksiteReadSerializer(read_only=True)

    class Meta:
        model = ShiftInstance
        fields = ["id", "date", "shift_template", "worksite", "status"]

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

# ---------- Body / Query helper serializers ----------
class ShiftRegisterBodySerializer(serializers.Serializer):
    employee = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")

class ShiftDirectAssignBodySerializer(serializers.Serializer):
    employee = serializers.IntegerField()

class ShiftInstanceQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to   = serializers.DateField(required=False)
    worksite  = serializers.IntegerField(required=False)

    def validate(self, attrs):
        df = attrs.get("date_from")
        dt = attrs.get("date_to")
        if df and dt and df > dt:
            raise serializers.ValidationError({"date_to": "date_to must be >= date_from"})
        return attrs
