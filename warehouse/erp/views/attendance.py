

# ─────────────────────────────────────────────────────────────
# erp/views/attendance.py
# ─────────────────────────────────────────────────────────────
from rest_framework import generics, permissions
from rest_framework.response import Response
from erp.serializers.attendance import AttendanceCreateSerializer, AttendanceRecordSerializer
from erp.models import AttendanceRecord
from django.utils import timezone

class CheckView(generics.CreateAPIView):
    serializer_class = AttendanceCreateSerializer
    permission_classes = [permissions.AllowAny]

class RecentAttendanceView(generics.ListAPIView):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        qs = AttendanceRecord.objects.all().order_by('-id')
        emp = self.request.query_params.get('employee_id')
        if emp: qs = qs.filter(employee_id=emp)
        days = int(self.request.query_params.get('days', 7))
        since = timezone.now() - timezone.timedelta(days=days)
        return qs.filter(created_at__gte=since)

