# -*- coding: utf-8 -*-
from __future__ import annotations
from rest_framework import serializers
from erp_the20.models import Attendance
from erp_the20.selectors.user_selector import ExternalUser

class AttendanceReadSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_email = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    template_code = serializers.CharField(source="shift_template.code", read_only=True)
    template_name = serializers.CharField(source="shift_template.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    work_mode_display = serializers.CharField(source="get_work_mode_display", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee_id",
            "shift_template",  # id
            "template_code",
            "template_name",
            "date",
            "ts_in",
            "ts_out",
            "source",
            "source_display",
            "work_mode",
            "work_mode_display",
            "bonus",
            "status",
            "status_display",
            "is_valid",
            "requested_by",
            "requested_at",
            "approved_by",
            "approved_at",
            "reject_reason",
            "deleted_at",
            "created_at",
            "updated_at",
            "employee_name",
            "employee_email",
            "requested_by_name",
            "approved_by_name",
        ]

    # ------- helpers dùng chung -------
    def _user(self, user_id: int) -> "ExternalUser|None":
        if user_id is None:
            return None
        users_map = self.context.get("users_map") or {}
        # keys trong users_map là int
        return users_map.get(int(user_id))

    # ------- getters cho FE -------
    def get_employee_name(self, obj):
        u = self._user(obj.employee_id)
        return u.fullname if u else None

    def get_employee_email(self, obj):
        u = self._user(obj.employee_id)
        return u.mail if u else None

    def get_requested_by_name(self, obj):
        u = self._user(obj.requested_by)
        return u.fullname if u else None

    def get_approved_by_name(self, obj):
        u = self._user(obj.approved_by)
        return u.fullname if u else None


# ---------- Write payloads ----------
class AttendanceCreateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    shift_template = serializers.IntegerField()
    date = serializers.DateField()
    ts_in = serializers.DateTimeField(required=False, allow_null=True)
    ts_out = serializers.DateTimeField(required=False, allow_null=True)
    source = serializers.ChoiceField(choices=Attendance.Source.choices, default=Attendance.Source.WEB)
    work_mode = serializers.ChoiceField(choices=Attendance.WorkMode.choices, default=Attendance.WorkMode.ONSITE)
    bonus = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0.00")


class AttendanceUpdateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()  # ai đang sửa (để check quyền manager nếu cần)
    shift_template = serializers.IntegerField(required=False)
    date = serializers.DateField(required=False)
    ts_in = serializers.DateTimeField(required=False, allow_null=True)
    ts_out = serializers.DateTimeField(required=False, allow_null=True)
    source = serializers.ChoiceField(choices=Attendance.Source.choices, required=False)
    work_mode = serializers.ChoiceField(choices=Attendance.WorkMode.choices, required=False)
    bonus = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    requested_by = serializers.IntegerField(required=False)


class CancelSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()


class ManagerCancelSerializer(serializers.Serializer):
    manager_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ApproveDecisionSerializer(serializers.Serializer):
    manager_id = serializers.IntegerField()
    approve = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    override_overlap = serializers.BooleanField(required=False, default=False)


class SearchFiltersSerializer(serializers.Serializer):
    employee_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)  # CSV "0,1" hoặc label
    is_valid = serializers.CharField(required=False)
    work_mode = serializers.CharField(required=False)     # CSV
    source = serializers.CharField(required=False)        # CSV
    template_code = serializers.CharField(required=False) # CSV
    template_name = serializers.CharField(required=False) # -> template_name_icontains

    approved_by = serializers.CharField(required=False)
    requested_by = serializers.CharField(required=False)

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    ts_in_from = serializers.CharField(required=False)
    ts_in_to = serializers.CharField(required=False)
    ts_out_from = serializers.CharField(required=False)
    ts_out_to = serializers.CharField(required=False)

    bonus_min = serializers.CharField(required=False)
    bonus_max = serializers.CharField(required=False)

    q = serializers.CharField(required=False)
    include_deleted = serializers.BooleanField(required=False)


# ---------- Batch register ----------
class BatchRegisterItemSerializer(serializers.Serializer):
    date = serializers.DateField()
    shift_template = serializers.IntegerField()
    ts_in = serializers.DateTimeField(required=False, allow_null=True)
    ts_out = serializers.DateTimeField(required=False, allow_null=True)

class BatchRegisterSerializer(serializers.Serializer):
    """
    Đăng ký hàng loạt cho 1 employee trong nhiều ngày/ca (tuần tới, v.v.)
    - items: danh sách {date, shift_template, (optional) ts_in, ts_out}
    - default_*: cấu hình mặc định cho tất cả item (có thể sửa tuỳ ý)
    """
    employee_id = serializers.IntegerField()
    items = BatchRegisterItemSerializer(many=True)

    default_source = serializers.ChoiceField(
        choices=Attendance.Source.choices, default=Attendance.Source.WEB
    )
    default_work_mode = serializers.ChoiceField(
        choices=Attendance.WorkMode.choices, default=Attendance.WorkMode.ONSITE
    )
    default_bonus = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0.00")


# ---------- Batch approve/reject ----------
class BatchDecisionItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()                     # attendance id
    approve = serializers.BooleanField()               # True=approve, False=reject
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    override_overlap = serializers.BooleanField(required=False, default=False)

class BatchDecisionSerializer(serializers.Serializer):
    manager_id = serializers.IntegerField()
    items = BatchDecisionItemSerializer(many=True)
