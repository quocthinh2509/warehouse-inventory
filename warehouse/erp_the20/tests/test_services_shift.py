import pytest
from django.core.exceptions import ValidationError
from erp_the20.services.shift_service import register_shift, approve_registration

@pytest.mark.django_db
def test_shift_register_and_approve(hr_admin, master_data, shift_data):
    emp = master_data["emp"]
    shift = shift_data["instance"]

    # Đăng ký
    reg = register_shift(employee=emp, shift_instance_id=shift.id, created_by=hr_admin, reason="join")
    assert reg.status == "pending"

    # Duyệt
    reg2 = approve_registration(registration_id=reg.id, approver=hr_admin)
    reg.refresh_from_db()
    assert reg2.id == reg.id
    assert reg.status == "approved"

@pytest.mark.django_db
def test_shift_register_capacity_limit(hr_admin, master_data, shift_data):
    # capacity = 2, đăng ký 2 người OK, người thứ 3 fail
    from erp_the20.models import Employee, Department, Position
    emp1 = master_data["emp"]
    dept = master_data["dept"]; pos = master_data["pos"]
    ws = master_data["ws"]; shift = shift_data["instance"]

    emp2 = Employee.objects.create(code="E002", full_name="B", department=dept, position=pos, default_worksite=ws)
    emp3 = Employee.objects.create(code="E003", full_name="C", department=dept, position=pos, default_worksite=ws)

    register_shift(employee=emp1, shift_instance_id=shift.id, created_by=hr_admin)
    register_shift(employee=emp2, shift_instance_id=shift.id, created_by=hr_admin)
    with pytest.raises(ValidationError):
        register_shift(employee=emp3, shift_instance_id=shift.id, created_by=hr_admin)
