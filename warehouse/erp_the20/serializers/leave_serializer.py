# -*- coding: utf-8 -*-
from __future__ import annotations
from rest_framework import serializers
from erp_the20.models import LeaveRequest


class LeaveRequestReadSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    leave_type_display = serializers.CharField(source="get_leave_type_display", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee_id",
            "paid",
            "leave_type",
            "leave_type_display",
            "start_date",
            "end_date",
            "hours",
            "reason",
            "status",
            "status_display",
            "decision_ts",
            "decided_by",
            "created_at",
            "updated_at",
        ]


# ===== Employee writes =====
class LeaveCreateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    manager_id = serializers.IntegerField()  # để gửi notify/validate quyền ngoài view
    paid = serializers.BooleanField(required=False, default=False)
    leave_type = serializers.ChoiceField(choices=LeaveRequest.LeaveType.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    hours = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class LeaveUpdateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()  # owner
    paid = serializers.BooleanField(required=False)
    leave_type = serializers.ChoiceField(choices=LeaveRequest.LeaveType.choices, required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    hours = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class LeaveCancelSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()


# ===== Manager decision =====
class LeaveManagerDecisionSerializer(serializers.Serializer):
    manager_id = serializers.IntegerField()
    approve = serializers.BooleanField()
