# -*- coding: utf-8 -*-
from rest_framework import serializers
from erp_the20.models import Handover, HandoverItem


class HandoverItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverItem
        fields = [
            "id", "handover", "title", "detail", "assignee_id",
            "status", "done_at", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "handover", "done_at", "created_at", "updated_at"]


class HandoverSerializer(serializers.ModelSerializer):
    items = HandoverItemSerializer(many=True, read_only=True)

    class Meta:
        model = Handover
        fields = [
            "id", "employee_id", "manager_id", "receiver_employee_id",
            "due_date", "status", "note", "items", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "items", "created_at", "updated_at"]
        extra_kwargs = {
            "employee_id": {"required": False},
            "manager_id": {"required": False},
            "receiver_employee_id": {"required": False},
            "due_date": {"required": False},
            "note": {"required": False},
            "status": {"required": False},
        }

    def update(self, instance, validated_data):
        # Cho phép update một số field an toàn
        allowed = {"manager_id", "receiver_employee_id", "due_date", "status", "note"}
        changed = []
        for k, v in validated_data.items():
            if k in allowed:
                setattr(instance, k, v)
                changed.append(k)
        if changed:
            changed.append("updated_at")
            instance.save(update_fields=changed)
        return instance
