import pytest
from rest_framework.test import APIClient
from erp_the20.models import Employee

@pytest.mark.django_db
def test_employee_list(user, master_data):
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/the20/employees/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert any(x["full_name"] == "Nguyen Van A" for x in resp.json())

@pytest.mark.django_db
def test_employee_create(user, master_data):
    client = APIClient()
    client.force_authenticate(user=user)
    dept = master_data["dept"].id
    ws = master_data["ws"].id

    payload = {
        "code": "E002",
        "full_name": "Tran Thi B",
        "department": dept,
        "default_worksite": ws,
        "email": "b@example.com",
    }
    resp = client.post("/the20/employees/", payload, format="json")
    assert resp.status_code == 201, resp.content
    assert Employee.objects.filter(code="E002").exists()

@pytest.mark.django_db
def test_employee_deactivate(user, master_data):
    client = APIClient()
    client.force_authenticate(user=user)
    emp = master_data["emp"]
    resp = client.post(f"/the20/employees/{emp.id}/deactivate/")
    assert resp.status_code == 200
    emp.refresh_from_db()
    assert emp.is_active is False
