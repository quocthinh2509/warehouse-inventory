from rest_framework import serializers
from .models import *

# Basic
class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id","code","full_name","base_salary","is_active"]

class WorksiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worksite
        fields = ["id","code","name","lat","lng","radius_m"]

# Shift
class ShiftTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = ["id","code","name","start_time","end_time","break_minutes","pay_coeff","is_overnight"]

class ShiftPlanSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), source="employee", write_only=True)
    template_id = serializers.PrimaryKeyRelatedField(queryset=ShiftTemplate.objects.all(), source="template", write_only=True)
    employee = EmployeeSerializer(read_only=True)
    template = ShiftTemplateSerializer(read_only=True)
    class Meta:
        model = ShiftPlan
        fields = ["id","date","slot","status","note","employee","template","employee_id","template_id"]

# Attendance
class AttendanceLogSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), source="employee", write_only=True, required=False)
    worksite_id = serializers.PrimaryKeyRelatedField(queryset=Worksite.objects.all(), source="worksite", write_only=True, required=False)
    shift_plan_id = serializers.PrimaryKeyRelatedField(queryset=ShiftPlan.objects.all(), source="shift_plan", write_only=True, required=False)
    employee = EmployeeSerializer(read_only=True)
    worksite = WorksiteSerializer(read_only=True)
    class Meta:
        model = AttendanceLog
        fields = ["id","type","occurred_at","employee","employee_id","worksite","worksite_id",
                  "shift_plan_id","lat","lng","accuracy_m","distance_m","source","device_id","note",
                  "is_valid","invalid_reason","created_at"]
        read_only_fields = ["distance_m","is_valid","invalid_reason","created_at"]

class AttendanceCheckSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=["IN","OUT"])
    worksite_id = serializers.IntegerField(required=False)
    lat = serializers.FloatField(required=False)
    lng = serializers.FloatField(required=False)
    accuracy_m = serializers.IntegerField(required=False)
    device_id = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)

# Leave
class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id","code","name","is_paid","default_unit"]

class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), source="employee", write_only=True)
    leave_type_id = serializers.PrimaryKeyRelatedField(queryset=LeaveType.objects.all(), source="leave_type", write_only=True)
    employee = EmployeeSerializer(read_only=True)
    leave_type = LeaveTypeSerializer(read_only=True)
    class Meta:
        model = LeaveRequest
        fields = ["id","employee","employee_id","leave_type","leave_type_id","date_from","date_to","unit","hours","reason","status","approver","created_at"]
        read_only_fields = ["status","approver","created_at"]

# Shift Registration
class ShiftRegistrationSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), source="employee", write_only=True)
    template_id = serializers.PrimaryKeyRelatedField(queryset=ShiftTemplate.objects.all(), source="template", write_only=True)
    employee = EmployeeSerializer(read_only=True)
    template = ShiftTemplateSerializer(read_only=True)
    class Meta:
        model = ShiftRegistration
        fields = ["id","employee","employee_id","date","slot","template","template_id","status","reason","created_at"]
        read_only_fields = ["status","created_at"]

# Timesheet & Payroll
class TimesheetEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimesheetEntry
        fields = "__all__"

class PayrollSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollSetting
        fields = "__all__"

class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = "__all__"

class PayrollLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollLine
        fields = "__all__"
