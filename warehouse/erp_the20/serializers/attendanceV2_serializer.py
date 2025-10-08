# # erp_the20/serializers/attendanceV2_serializer.py

# from __future__ import annotations
# from rest_framework import serializers
# from erp_the20.models import AttendanceSummaryV2


# class AttendanceSummaryV2ReadSerializer(serializers.ModelSerializer):
#     date = serializers.DateField(source="shift_instance.date", read_only=True)
#     template_code = serializers.CharField(source="shift_instance.template.code", read_only=True)
#     template_name = serializers.CharField(source="shift_instance.template.name", read_only=True)

#     class Meta:
#         model = AttendanceSummaryV2
#         fields = [
#             "id",
#             "employee_id",
#             "shift_instance",  # id
#             "date",
#             "template_code",
#             "template_name",
#             "ts_in",
#             "ts_out",
#             "work_mode",
#             "bonus",
#             "status",
#             "is_valid",
#             "requested_by",
#             "requested_at",
#             "approved_by",
#             "approved_at",
#             "reject_reason",
#         ]


# # ---------- Write payloads ----------

# class RegisterShiftSerializer(serializers.Serializer):
#     # ✅ thêm employee_id để đọc từ body
#     employee_id = serializers.IntegerField()
#     shift_instance_id = serializers.IntegerField()


# class UpdateRegistrationSerializer(serializers.Serializer):
#     employee_id = serializers.IntegerField()              # ✅
#     summary_id = serializers.IntegerField()
#     new_shift_instance_id = serializers.IntegerField()
#     requested_by = serializers.IntegerField(required=False)


# class DeleteRegistrationSerializer(serializers.Serializer):
#     # (không dùng trong view destroy vì lấy pk trên URL,
#     #  nhưng nếu muốn gửi body cho DELETE thì để ở đây)
#     employee_id = serializers.IntegerField(required=False)
#     summary_id = serializers.IntegerField(required=False)


# class CancelRegistrationSerializer(serializers.Serializer):
#     employee_id = serializers.IntegerField()              # ✅
#     summary_id = serializers.IntegerField()


# class ManagerCancelSerializer(serializers.Serializer):
#     manager_id = serializers.IntegerField()
#     summary_id = serializers.IntegerField()
#     reason = serializers.CharField(required=False, allow_blank=True, default="")


# class ApproveDecisionSerializer(serializers.Serializer):
#     manager_id = serializers.IntegerField()
#     summary_id = serializers.IntegerField(required=False)
#     approve = serializers.BooleanField()
#     reason = serializers.CharField(required=False, allow_blank=True, default="")
#     override_overlap = serializers.BooleanField(required=False, default=False)

# class BulkRegisterSerializer(serializers.Serializer):
#     employee_id = serializers.IntegerField()
#     shift_instance_ids = serializers.ListField(
#         child=serializers.IntegerField(), allow_empty=False
#     )
#     requested_by = serializers.IntegerField(required=False)

# class SearchFiltersSerializer(serializers.Serializer):
#     employee_id = serializers.CharField(required=False)
#     status = serializers.CharField(required=False)
#     is_valid = serializers.CharField(required=False)
#     work_mode = serializers.CharField(required=False)
#     source = serializers.CharField(required=False)
#     template_code = serializers.CharField(required=False)
#     template_name = serializers.CharField(required=False)  # mapped -> template_name_icontains

#     approved_by = serializers.CharField(required=False)
#     requested_by = serializers.CharField(required=False)

#     shift_date_from = serializers.DateField(required=False)
#     shift_date_to = serializers.DateField(required=False)
#     ts_in_from = serializers.CharField(required=False)
#     ts_in_to = serializers.CharField(required=False)
#     ts_out_from = serializers.CharField(required=False)
#     ts_out_to = serializers.CharField(required=False)

#     bonus_min = serializers.CharField(required=False)
#     bonus_max = serializers.CharField(required=False)

#     q = serializers.CharField(required=False)
