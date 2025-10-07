# attendance_serializer.py
from rest_framework import serializers
from erp_the20.models import AttendanceEvent, AttendanceSummary, AttendanceCorrection, AttendanceSummaryV2
from erp_the20.serializers.shift_serializer import ShiftInstanceReadSerializer



# =========================
# AttendanceEvent
# =========================
class AttendanceEventWriteSerializer(serializers.ModelSerializer):
    employee = serializers.IntegerField()  # thay vì ForeignKey

    class Meta:
        model = AttendanceEvent
        fields = [
            "id",
            "employee",
            "shift_instance",
            "event_type",
            "ts",
            "source",
            "is_valid",
            "raw_payload",
        ]


class AttendanceEventReadSerializer(serializers.ModelSerializer):
    employee = serializers.IntegerField(read_only=True)  # chỉ trả về int
    shift_instance = ShiftInstanceReadSerializer(read_only=True)

    class Meta:
        model = AttendanceEvent
        fields = [
            "id",
            "employee",
            "shift_instance",
            "event_type",
            "ts",
            "source",
            "is_valid",
            "raw_payload",
        ]


# =========================
# AttendanceSummary
# =========================
class AttendanceSummaryWriteSerializer(serializers.ModelSerializer):
    employee = serializers.IntegerField()

    class Meta:
        model = AttendanceSummary
        fields = [
            "id",
            "employee_id",
            "date",
            "planned_minutes",
            "worked_minutes",
            "late_minutes",
            "early_leave_minutes",
            "overtime_minutes",
            "on_leave"
            "segments",
            "status",
            "notes",
            "events",
        ]


class AttendanceSummaryReadSerializer(serializers.ModelSerializer):
    # on_leave có thể là FK; để gọn, trả về id nếu có
    # on_leave_id = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSummary
        fields = [
            "id",
            "employee_id",
            "date",
            "planned_minutes",
            "worked_minutes",
            "late_minutes",
            "early_leave_minutes",
            "overtime_minutes",
            "status",
            "notes",
            "events",     # snapshot events (JSONField)
            "segments",   # nếu để trống vẫn ok
            "on_leave",
        ]

    # def get_on_leave_id(self, obj):
    #     try:
    #         return obj.on_leave_id if getattr(obj, "on_leave_id", None) else None
    #     except Exception:
    #         return None


# =========================
# AttendanceCorrection
# =========================
class AttendanceCorrectionWriteSerializer(serializers.ModelSerializer):
    employee = serializers.IntegerField()

    class Meta:
        model = AttendanceCorrection
        fields = [
            "id",
            "employee",
            "date",
            "type",
            "requested_by",
            "status",
            "approver",
            "changeset",
        ]


class AttendanceCorrectionReadSerializer(serializers.ModelSerializer):
    employee = serializers.IntegerField(read_only=True)

    class Meta:
        model = AttendanceCorrection
        fields = [
            "id",
            "employee",
            "date",
            "type",
            "requested_by",
            "status",
            "approver",
            "changeset",
        ]

# class AttendanceSummaryV2ReadSerializer(serializers.ModelSerializer):
