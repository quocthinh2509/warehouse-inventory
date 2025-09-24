import pytest
from datetime import date
from django.core.exceptions import ValidationError
from erp_the20.services.leave_service import create_leave_request, approve_leave_request
from erp_the20.models import LeaveRequest

@pytest.mark.django_db
def test_leave_request_and_approve(hr_admin, master_data, leave_type, leave_balance):
    emp = master_data["emp"]
    lt = leave_type

    lr = create_leave_request(employee=emp, leave_type=lt, start_date=date(2025,9,20), end_date=date(2025,9,20), reason="personal")
    assert lr.status == "pending"

    lr2 = approve_leave_request(leave_request_id=lr.id, approver=hr_admin)
    lr.refresh_from_db()
    assert lr.status == "approved"
    assert lr2.id == lr.id

@pytest.mark.django_db
def test_leave_insufficient_balance(master_data, leave_type):
    emp = master_data["emp"]
    lt = leave_type

    # Không có LeaveBalance hoặc closing = 0 => raise
    with pytest.raises(ValidationError):
        create_leave_request(employee=emp, leave_type=lt, start_date=date(2025,9,20), end_date=date(2025,9,25))
