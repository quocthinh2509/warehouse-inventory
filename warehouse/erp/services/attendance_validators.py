# ─────────────────────────────────────────────────────────────
# erp/services/attendance_validators.py
# ─────────────────────────────────────────────────────────────
from datetime import timedelta
from math import radians, cos, sin, asin, sqrt
from django.utils import timezone
from django.db.models import Q
from erp.models import AttendanceRecord, Worksite

DUP_WINDOW_MINUTES = 3


def within_radius_meters(lat1, lng1, lat2, lng2):
    R = 6371000.0
    dlat = radians(float(lat2) - float(lat1))
    dlng = radians(float(lng2) - float(lng1))
    a = sin(dlat/2)**2 + cos(radians(float(lat1))) * cos(radians(float(lat2))) * sin(dlng/2)**2
    c = 2 * asin(sqrt(a))
    return R * c


def validate_new_check(employee, when, kind='in'):
    window = timedelta(minutes=DUP_WINDOW_MINUTES)
    qs = AttendanceRecord.objects.filter(employee=employee)
    if kind == 'in':
        qs = qs.filter(check_in_at__gte=when - window, check_in_at__lte=when + window)
    else:
        qs = qs.filter(check_out_at__gte=when - window, check_out_at__lte=when + window)
    if qs.exists():
        return False, 'duplicate_within_window'
    return True, ''


def validate_geo(worksite: Worksite, lat, lng, accuracy_m: int | None):
    if worksite.latitude is None or worksite.longitude is None:
        return True, ''
    if lat is None or lng is None:
        return False, 'missing_location'
    dist = within_radius_meters(lat, lng, worksite.latitude, worksite.longitude)
    if accuracy_m is not None and accuracy_m > 150:
        return False, 'low_accuracy'
    if dist > worksite.radius_m:
        return False, f'out_of_radius({int(dist)}m)'
    return True, ''