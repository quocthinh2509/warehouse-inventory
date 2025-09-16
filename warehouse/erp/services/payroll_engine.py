
# ─────────────────────────────────────────────────────────────
# erp/services/payroll_engine.py
# ─────────────────────────────────────────────────────────────
from decimal import Decimal
from erp.models import AttendanceRecord

DAILY_DENOMINATOR = Decimal('26')


def compute_days_worked(employee, start_date, end_date):
    qs = AttendanceRecord.objects.filter(employee=employee, check_in_at__date__gte=start_date, check_in_at__date__lte=end_date)
    return Decimal(qs.values_list('check_in_at__date', flat=True).distinct().count())


def compute_payline(employee, period, base_salary: Decimal | None = None):
    base = base_salary if base_salary is not None else employee.base_salary
    days = compute_days_worked(employee, period.start_date, period.end_date)
    daily_rate = (base or Decimal('0')) / DAILY_DENOMINATOR if base and base > 0 else Decimal('0')
    gross = daily_rate * days
    return {
        'employee_id': employee.id,
        'days_worked': days,
        'base_salary': base or Decimal('0'),
        'deductions': Decimal('0'),
        'bonuses': Decimal('0'),
        'net_pay': gross,
    }
