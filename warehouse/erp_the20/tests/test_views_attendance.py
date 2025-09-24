import pytest
from datetime import datetime, timezone as tz
from unittest.mock import patch
from rest_framework.test import APIClient

UTC7 = tz.utc

@pytest.mark.django_db
def test_checkin_checkout_api(user, master_data):
    client = APIClient()
    client.force_authenticate(user=user)
    emp = master_data["emp"]; ws = master_data["ws"]

    with patch("erp_the20.services.attendance_service.validate_geofence", return_value=8.0):
        r1 = client.post("/the20/attend/check-in/", {
            "employee": emp.id, "ts": "2025-09-18T09:00:00Z", "lat": 10.77, "lng": 106.69, "accuracy_m": 25, "worksite": ws.id
        }, format="json")
        assert r1.status_code == 201, r1.content

        r2 = client.post("/the20/attend/check-out/", {
            "employee": emp.id, "ts": "2025-09-18T17:10:00Z", "lat": 10.77, "lng": 106.69, "accuracy_m": 25, "worksite": ws.id
        }, format="json")
        assert r2.status_code == 200, r2.content

    # summary API
    r3 = client.get(f"/the20/attend/summary/?employee={emp.id}")
    assert r3.status_code == 200
    assert isinstance(r3.json(), list)
    assert len(r3.json()) >= 1
