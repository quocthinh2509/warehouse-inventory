from rest_framework import serializers
from erp_the20.models import LeaveType, LeaveBalance, LeaveRequest

class LeaveTypeWWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "code", "name", "description"]

class LeaveBalanceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveBalance
        fields = ["id", "employee", "leave_type", "period" , "opening", "accrued", "used"]


class LeaveRequestWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ["id", "employee", "leave_type", "start_date", "end_date","hours" "reason", "status","approver", "decision_ts"]


class LeaveTypeReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "code", "name", "description"]
        read_only_fields = ["id", "code", "name", "description"]

class LeaveBalanceReadSerializer(serializers.ModelSerializer):
    leave_type = LeaveTypeReadSerializer(read_only=True)
    class Meta:
        model = LeaveBalance
        fields = ["id", "employee", "leave_type", "period" , "opening", "accrued", "used"]
        read_only_fields = ["id", "employee", "leave_type", "period" , "opening", "accrued", "used"]

class LeaveRequestReadSerializer(serializers.ModelSerializer):
    leave_type = LeaveTypeReadSerializer(read_only=True)
    class Meta:
        model = LeaveRequest
        fields = ["id", "employee", "leave_type", "start_date", "end_date","hours" "reason", "status","approver", "decision_ts"]
        read_only_fields = ["id", "employee", "leave_type", "start_date", "end_date","hours" "reason", "status","approver", "decision_ts"]