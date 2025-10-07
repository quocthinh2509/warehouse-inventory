# -*- coding: utf-8 -*-
from __future__ import annotations
from rest_framework import serializers
from erp_the20.models import LeaveRequest


class LeaveRequestReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee_id",
            "paid",
            "start_date",
            "end_date",
            "hours",
            "reason",
            "status",
            "decision_ts",
            "decided_by",
            "created_at",
            "updated_at",
        ]


# --------- Employee writes ---------

class LeaveCreateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    manager_id  = serializers.IntegerField()  # <-- thêm: dùng để gửi mail cho quản lý
    paid = serializers.BooleanField(required=False, default=False)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    hours = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class LeaveUpdateSerializer(serializers.Serializer):
    # pk nằm trên URL; payload có thể gửi lại employee_id để dùng chung validate
    employee_id = serializers.IntegerField()
    paid = serializers.BooleanField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    hours = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class LeaveCancelSerializer(serializers.Serializer):
    # nhân viên tự huỷ: employee_id chính là người tạo
    employee_id = serializers.IntegerField()


# --------- Manager decisions ---------

class LeaveManagerDecisionSerializer(serializers.Serializer):
    manager_id = serializers.IntegerField()
    approve = serializers.BooleanField()
    # Có thể bổ sung decision_note nếu cần trong tương lai
