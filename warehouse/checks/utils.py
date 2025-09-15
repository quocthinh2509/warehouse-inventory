# utils.py
from math import radians, sin, cos, sqrt, atan2
from checks.models import Worksite, EmployeeWorksite

def haversine_m(lat1, lon1, lat2, lon2) -> int:
    R = 6371000.0  # mét
    φ1, φ2 = radians(lat1), radians(lat2)
    dφ = radians(lat2 - lat1)
    dλ = radians(lon2 - lon1)
    a = sin(dφ/2)**2 + cos(φ1)*cos(φ2)*sin(dλ/2)**2
    return int(R * 2 * atan2(sqrt(a), sqrt(1 - a)))

def nearest_allowed_worksite(employee, lat, lng):
    """
    Nếu employee có rule EmployeeWorksite -> chỉ chọn trong đó.
    Nếu không -> chọn trong tất cả Worksite active.
    Trả về (worksite, distance_m) hoặc (None, None).
    """
    qs = Worksite.objects.filter(active=True)
    if EmployeeWorksite.objects.filter(employee=employee).exists():
        qs = qs.filter(employeeworksite__employee=employee)

    nearest, min_d = None, 10**12
    for ws in qs:
        d = haversine_m(lat, lng, ws.lat, ws.lng)
        if d < min_d:
            nearest, min_d = ws, d
    return nearest, (min_d if nearest else None)
