
# ─────────────────────────────────────────────────────────────
# erp/views/hr.py
# ─────────────────────────────────────────────────────────────
from rest_framework import viewsets, permissions
from erp.models import Department, Worksite, Shift, Employee, LeaveType, LeaveRequest
from erp.serializers.hr import DepartmentSerializer, WorksiteSerializer, ShiftSerializer, EmployeeSerializer, LeaveTypeSerializer, LeaveRequestSerializer

class BaseRW(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny]

class DepartmentViewSet(BaseRW):
    queryset = Department.objects.all().order_by('code')
    serializer_class = DepartmentSerializer

class WorksiteViewSet(BaseRW):
    queryset = Worksite.objects.all().order_by('code')
    serializer_class = WorksiteSerializer

class ShiftViewSet(BaseRW):
    queryset = Shift.objects.all().order_by('code')
    serializer_class = ShiftSerializer

class EmployeeViewSet(BaseRW):
    queryset = Employee.objects.all().order_by('code')
    serializer_class = EmployeeSerializer

class LeaveTypeViewSet(BaseRW):
    queryset = LeaveType.objects.all().order_by('code')
    serializer_class = LeaveTypeSerializer

class LeaveRequestViewSet(BaseRW):
    queryset = LeaveRequest.objects.all().order_by('-start_date')
    serializer_class = LeaveRequestSerializer

