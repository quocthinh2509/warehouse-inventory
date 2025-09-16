
# ─────────────────────────────────────────────────────────────
# erp/serializers/hr.py
# ─────────────────────────────────────────────────────────────
from rest_framework import serializers
from erp.models import Department, Worksite, Shift, Employee, LeaveType, LeaveRequest

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta: model = Department; fields = ['id','code','name','status']

class WorksiteSerializer(serializers.ModelSerializer):
    class Meta: model = Worksite; fields = ['id','code','name','latitude','longitude','radius_m','status']

class ShiftSerializer(serializers.ModelSerializer):
    class Meta: model = Shift; fields = ['id','code','name','start_time','end_time','break_minutes','status']

class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    class Meta: model = Employee; fields = ['id','code','full_name','email','phone','department','department_name','base_salary','default_shift','default_worksite','is_active','status']

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta: model = LeaveType; fields = ['id','code','name','paid','status']

class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    class Meta: model = LeaveRequest; fields = ['id','employee','employee_name','leave_type','start_date','end_date','reason','status','approved_by','created_at']

