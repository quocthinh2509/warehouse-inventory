# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime, timedelta
from rest_framework import serializers
from django.utils import timezone

from erp_the20.models import Attendance, LeaveRequest
from erp_the20.selectors.user_selector import ExternalUser

class LeaveBriefSerializer(serializers.ModelSerializer):
    leave_type_display = serializers.CharField(source="get_leave_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "leave_type", "leave_type_display",
            "status", "status_display",
            "paid",
            "start_date", "end_date",
            "hours",
            "reason",
        ]

class ShiftOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    employee_id = serializers.IntegerField()
    shift_template = serializers.IntegerField()
    template_code = serializers.CharField()
    template_name = serializers.CharField()
    date = serializers.DateField()
    sched_start = serializers.DateTimeField()
    sched_end = serializers.DateTimeField()
    is_current = serializers.BooleanField()
    starts_in_minutes = serializers.IntegerField()
    ends_in_minutes = serializers.IntegerField()
    status = serializers.IntegerField()
    status_display = serializers.CharField()

class PunchSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=[("in","in"),("out","out")])
    ts = serializers.DateTimeField(required=False)  # mặc định server now nếu không truyền

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

    # ---- Dynamic fields for FE (NOT saved to DB) ----
    sched_start = serializers.SerializerMethodField()
    sched_end = serializers.SerializerMethodField()
    break_minutes = serializers.SerializerMethodField()
    sched_minutes = serializers.SerializerMethodField()
    ts_in_final = serializers.SerializerMethodField()
    ts_out_final = serializers.SerializerMethodField()
    on_leave_id = serializers.IntegerField(source="on_leave.id", read_only=True)
    on_leave = LeaveBriefSerializer(read_only=True)

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
            "ts_in_final",
            "ts_out_final",
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
            # === persisted minutes ===
            "worked_minutes",
            "paid_minutes",
            "employee_name",
            "employee_email",
            "requested_by_name",
            "approved_by_name",
            # === dynamic schedule ===
            "sched_start",
            "sched_end",
            "break_minutes",
            "sched_minutes",
            "on_leave_id", "on_leave",
        ]

    # ------- helpers dùng chung -------
    def _user(self, user_id: int) -> "ExternalUser|None":
        if user_id is None:
            return None
        users_map = self.context.get("users_map") or {}
        return users_map.get(int(user_id))

    def _local_iso(self, dt):
        if not dt:
            return None
        return timezone.localtime(dt).isoformat()

    def _mins(self, a, b) -> int:
        if not a or not b:
            return 0
        return max(0, int((b - a).total_seconds() // 60))

    # ------- getters: users -------
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

    # ------- schedule helpers for FE -------
    def _sched_window(self, obj):
        t = obj.shift_template
        if not t or not obj.date:
            return None, None, 0
        tz = timezone.get_current_timezone()
        start_naive = datetime.combine(obj.date, t.start_time)
        end_naive = datetime.combine(obj.date, t.end_time)
        if getattr(t, "overnight", False) or t.end_time <= t.start_time:
            end_naive = end_naive + timedelta(days=1)
        start_dt = timezone.make_aware(start_naive, tz) if not timezone.is_aware(start_naive) else start_naive
        end_dt = timezone.make_aware(end_naive, tz) if not timezone.is_aware(end_naive) else end_naive
        break_min = int(getattr(t, "break_minutes", 0) or 0)
        return start_dt, end_dt, break_min

    # ------- schedule fields -------
    def get_sched_start(self, obj):
        s, _, _ = self._sched_window(obj)
        return self._local_iso(s)

    def get_sched_end(self, obj):
        _, e, _ = self._sched_window(obj)
        return self._local_iso(e)

    def get_break_minutes(self, obj):
        _, _, br = self._sched_window(obj)
        return br

    def get_sched_minutes(self, obj):
        s, e, br = self._sched_window(obj)
        return max(0, self._mins(s, e) - (br or 0)) if s and e else 0

    # ------- final (clamped) fields -------
    def get_ts_in_final(self, obj):
        if not obj.ts_in:
            return None
        s, e, _ = self._sched_window(obj)
        if not s or not e:
            return self._local_iso(obj.ts_in)

        cin = obj.ts_in
        if cin < s:
            cin = s
        if cin > e:
            cin = e

        if obj.ts_out:
            cout = obj.ts_out
            if cout > e:
                cout = e
            if cout < s:
                cout = s
            if cout <= cin:
                return None

        return self._local_iso(cin)

    def get_ts_out_final(self, obj):
        if not obj.ts_out:
            return None
        s, e, _ = self._sched_window(obj)
        if not s or not e:
            return self._local_iso(obj.ts_out)

        cout = obj.ts_out
        if cout > e:
            cout = e
        if cout < s:
            cout = s

        if obj.ts_in:
            cin = obj.ts_in
            if cin < s:
                cin = s
            if cin > e:
                cin = e
            if cout <= cin:
                return None

        return self._local_iso(cout)


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
    employee_id = serializers.IntegerField()
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
    status = serializers.CharField(required=False)
    is_valid = serializers.CharField(required=False)
    work_mode = serializers.CharField(required=False)
    source = serializers.CharField(required=False)
    template_code = serializers.CharField(required=False)
    template_name = serializers.CharField(required=False)
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

class BatchRegisterItemSerializer(serializers.Serializer):
    date = serializers.DateField()
    shift_template = serializers.IntegerField()
    ts_in = serializers.DateTimeField(required=False, allow_null=True)
    ts_out = serializers.DateTimeField(required=False, allow_null=True)

class BatchRegisterSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    items = BatchRegisterItemSerializer(many=True)
    default_source = serializers.ChoiceField(choices=Attendance.Source.choices, default=Attendance.Source.WEB)
    default_work_mode = serializers.ChoiceField(choices=Attendance.WorkMode.choices, default=Attendance.WorkMode.ONSITE)
    default_bonus = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0.00")

class BatchDecisionItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    approve = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    override_overlap = serializers.BooleanField(required=False, default=False)

class BatchDecisionSerializer(serializers.Serializer):
    manager_id = serializers.IntegerField()
    items = BatchDecisionItemSerializer(many=True)
