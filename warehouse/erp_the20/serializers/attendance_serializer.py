# attendance_serializer.py
from rest_framework import serializers
from erp_the20.models import AttendanceEvent, AttendanceSummary, AttendanceCorrection
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
            "employee",
            "date",
            "planned_minutes",
            "worked_minutes",
            "late_minutes",
            "early_leave_minutes",
            "overtime_minutes",
            "segments",
            "status",
            "notes",
        ]


class AttendanceSummaryReadSerializer(serializers.ModelSerializer):
    employee = serializers.IntegerField(read_only=True)

    class Meta:
        model = AttendanceSummary
        fields = [
            "id",
            "employee",
            "date",
            "planned_minutes",
            "worked_minutes",
            "late_minutes",
            "early_leave_minutes",
            "overtime_minutes",
            "segments",
            "status",
            "notes",
        ]


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
