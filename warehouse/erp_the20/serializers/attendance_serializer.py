# attendance_serializer.py
from rest_framework import serializers
from erp_the20.models import AttendanceEvent, AttendanceSummary

class AttendanceEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceEvent
        fields = "__all__"

class AttendanceCheckSerializer(serializers.Serializer):
    employee = serializers.IntegerField()
    # Server tự set timestamp, client không cần gửi
    ts = serializers.DateTimeField(required=False, read_only=True)

    shift_instance = serializers.IntegerField(required=False, allow_null=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    accuracy_m = serializers.FloatField(required=False, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True)
    worksite = serializers.IntegerField(required=False, allow_null=True)

class AttendanceSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSummary
        fields = "__all__"
