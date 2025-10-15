# Load tất cả model vào namespace erp_the20.models
from .mixins import TimeStampedModel

from .core import Department, Position
from .shift import ShiftTemplate
from .leave import LeaveRequest
from .attendance import Attendance
from .settings import HolidayCalendar, ApprovalFlow
from .notification import Notification
from .audit import AuditLog
from .proposal import Proposal
from .employee import EmployeeProfile
from .handover import Handover, HandoverItem

__all__ = [
    "TimeStampedModel",
    "Department", "Position",
    "ShiftTemplate",
    "LeaveRequest",
    "Attendance",
    "HolidayCalendar", "ApprovalFlow",
    "Notification",
    "AuditLog",
    "Proposal",
    "EmployeeProfile",
    "Handover", "HandoverItem",
]
