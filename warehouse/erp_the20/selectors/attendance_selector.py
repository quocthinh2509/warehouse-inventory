# attendance_selector.py
from erp_the20.models import AttendanceEvent, AttendanceSummary

def get_last_event(employee_id: int):
    return AttendanceEvent.objects.filter(employee_id=employee_id).order_by("-ts").first()

def get_summary(employee_id: int, date):
    return AttendanceSummary.objects.filter(employee_id=employee_id, date=date).first()

def list_summaries(employee_id: int):
    return AttendanceSummary.objects.filter(employee_id=employee_id).order_by("-date")

def list_all_summaries():
    return AttendanceSummary.objects.all().order_by("-date")

def list_summaries_by_date(date):
    return AttendanceSummary.objects.filter(date=date).order_by("employee__full_name")
