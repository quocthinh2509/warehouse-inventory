
# ─────────────────────────────────────────────────────────────
# erp/serializers/payroll.py
# ─────────────────────────────────────────────────────────────
from rest_framework import serializers
from erp.models import PayrollPeriod, PayrollLine, Employee
from erp.services.payroll_engine import compute_payline

class PayrollPeriodSerializer(serializers.ModelSerializer):
    class Meta: model = PayrollPeriod; fields = ['id','code','start_date','end_date','locked','created_at']

class PayrollLineSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    class Meta: model = PayrollLine; fields = ['id','period','employee','employee_name','base_salary','days_worked','overtime_hours','leave_hours','deductions','bonuses','net_pay','created_at']

class PayrollPreviewSerializer(serializers.Serializer):
    period_id = serializers.IntegerField()
    def validate(self, attrs):
        try:
            attrs['period'] = PayrollPeriod.objects.get(pk=attrs['period_id'])
        except PayrollPeriod.DoesNotExist:
            raise serializers.ValidationError({'detail':'period_not_found'})
        return attrs
    def create(self, validated):
        period = validated['period']
        data = []
        for emp in Employee.objects.filter(is_active=True):
            data.append(compute_payline(emp, period))
        return data

