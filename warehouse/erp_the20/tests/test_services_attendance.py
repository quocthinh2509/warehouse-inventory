import pytest
from datetime import datetime, timezone as tz
from unittest.mock import patch
from django.core.exceptions import ValidationError
from erp_the20.services.attendance_service import check_in, check_out
from erp_the20.models import AttendanceSummary

UTC7 = tz.utc  # đơn giản hóa trong test, bạn có thể thay bằng +07:00 nếu cần

@pytest.mark.django_db
def test_check_in_out_success(master_data):
    emp = master_data["emp"]
    ws = master_data["ws"]

    # Mock validate_geofence để luôn pass, tránh phụ thuộc GPS thật
    with patch("erp_the20.services.attendance_service.validate_geofence", return_value=10.0):
        ci = check_in(employee=emp, ts=datetime(2025,9,18,9,0,tzinfo=UTC7), lat=10.77, lng=106.69, accuracy_m=20, worksite=ws)
        assert ci.event_type == "check_in"
        co = check_out(employee=emp, ts=datetime(2025,9,18,17,5,tzinfo=UTC7), lat=10.77, lng=106.69, accuracy_m=20, worksite=ws)
        assert co.event_type == "check_out"

    # Tổng hợp minutes
    s = AttendanceSummary.objects.get(employee=emp, date=datetime(2025,9,18,tzinfo=UTC7).date())
    assert s.worked_minutes >= 480  # 8h = 480, với 17:05 có thể >480

@pytest.mark.django_db
def test_double_check_in_blocked(master_data):
    emp = master_data["emp"]
    with patch("erp_the20.services.attendance_service.validate_geofence", return_value=5.0):
        check_in(employee=emp, ts=datetime(2025,9,18,9,0,tzinfo=UTC7))
        with pytest.raises(ValidationError):
            check_in(employee=emp, ts=datetime(2025,9,18,10,0,tzinfo=UTC7))

@pytest.mark.django_db
def test_check_out_without_check_in(master_data):
    emp = master_data["emp"]
    with pytest.raises(ValidationError):
        check_out(employee=emp, ts=datetime(2025,9,18,17,0,tzinfo=UTC7))
