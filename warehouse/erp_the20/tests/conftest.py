import pytest
from django.contrib.auth import get_user_model
from decimal import Decimal
from erp_the20.models import Department, Worksite, Position, Employee, ShiftTemplate, ShiftInstance, LeaveType, LeaveBalance

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(username="tester", password="pass")

@pytest.fixture
def hr_admin(db):
    return User.objects.create_user(username="hradmin", password="pass", is_staff=True, is_superuser=True)

@pytest.fixture
def master_data(db):
    dept = Department.objects.create(code="D1", name="Sales")
    ws = Worksite.objects.create(code="WS1", name="HCM HQ", lat=10.77, lng=106.69, radius_m=300)
    pos = Position.objects.create(code="P1", name="Staff", default_department=dept)
    emp = Employee.objects.create(
        code="E001", full_name="Nguyen Van A", department=dept, position=pos,
        default_worksite=ws, base_salary=Decimal("10000000.00")
    )
    return {"dept": dept, "ws": ws, "pos": pos, "emp": emp}

@pytest.fixture
def shift_data(db, master_data):
    from datetime import time, date
    st = ShiftTemplate.objects.create(
        code="ST1", name="HC", start_time=time(8,0), end_time=time(17,0),
        break_minutes=60, overnight=False, weekly_days="1,2,3,4,5",
        default_worksite=master_data["ws"]
    )
    si = ShiftInstance.objects.create(
        template=st, date=date.today(), worksite=master_data["ws"], capacity=2, status="open"
    )
    return {"template": st, "instance": si}

@pytest.fixture
def leave_type(db):
    return LeaveType.objects.create(code="AL", name="Annual Leave", paid=True)

@pytest.fixture
def leave_balance(db, master_data, leave_type):
    # cấp sẵn 12 ngày/năm
    from erp_the20.models import LeaveBalance
    return LeaveBalance.objects.create(
        employee=master_data["emp"], leave_type=leave_type, period="2025",
        opening=0, accrued=12, used=0, carry_in=0, carry_out=0, closing=12
    )
