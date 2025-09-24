from erp_the20.models import LeaveBalance, LeaveRequest

def get_balance(employee_id: int, leave_type_id: int, period: str):
    return LeaveBalance.objects.filter(employee_id=employee_id, leave_type_id=leave_type_id, period=period).first()

def list_requests(employee_id: int):
    return LeaveRequest.objects.filter(employee_id=employee_id).select_related("leave_type")
