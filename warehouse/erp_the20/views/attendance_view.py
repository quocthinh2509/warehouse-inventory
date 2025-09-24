# attendance_view.py (đoạn đã chỉnh)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.utils import timezone

from erp_the20.models import Employee, AttendanceSummary
from erp_the20.serializers.attendance_serializer import (
    AttendanceCheckSerializer, AttendanceEventSerializer, AttendanceSummarySerializer
)
from erp_the20.services.attendance_service import add_check_in, add_check_out

# >>> NEW: import service xác thực LAN
from erp_the20.services.local_gate_service import require_local_access_token

from .utils import (
    extend_schema, extend_schema_view, OpenApiExample, OpenApiResponse,
    q_int, q_date, std_errors
)

def _get_active_employee(emp_id: int):
    emp = Employee.objects.filter(id=emp_id, is_active=True).first()
    if not emp:
        raise DRFValidationError({"employee": "Employee not found or inactive."})
    return emp


# --- Check In ---
@extend_schema_view(
    post=extend_schema(
        tags=["Attendance"],
        summary="Check in",
        description=(
            "Chỉ cho phép khi có X-Local-Access (JWT được cấp sau khi Agent LAN xác thực). "
            "Server tự gán thời điểm check-in = thời gian hiện tại (timezone-aware)."
        ),
        request=AttendanceCheckSerializer,
        responses={
            201: OpenApiResponse(AttendanceEventSerializer, description="Tạo sự kiện check-in"),
            **std_errors()
        },
        examples=[
            OpenApiExample(
                "Body mẫu (ts bỏ qua / không cần gửi)",
                request_only=True,
                value={
                    "employee": 1,
                    "lat": 10.77,
                    "lng": 106.69,
                    "accuracy_m": 18,
                    "worksite": 3,
                    "shift_instance": 12,
                    "source": "web",
                },
            ),
        ],
    )
)
class CheckInView(APIView):
    def post(self, request):
        # 1) BẮT BUỘC: xác thực LAN qua local_access_token trong header
        local_token = request.headers.get("X-Local-Access")
        try:
            claims = require_local_access_token(local_token)  # ném lỗi nếu không hợp lệ
        except Exception as exc:
            raise DRFValidationError({"detail": str(exc)})

        # 2) Parse input như cũ
        ser = AttendanceCheckSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        emp = _get_active_employee(v["employee"])
        now = timezone.now()  # thời gian server

        # (tuỳ chọn) map agent_code -> worksite_id nếu muốn enforce địa điểm
        agent_code = claims.get("agent_code")
        # worksite_id = map_agent_to_worksite_id(agent_code)  # nếu có, bạn tự cài selector
        worksite_id = v.get("worksite")

        try:
            ev = add_check_in(
                employee=emp,
                ts=now,
                lat=v.get("lat"),
                lng=v.get("lng"),
                accuracy_m=v.get("accuracy_m"),
                source=v.get("source") or "web",
                shift_instance_id=v.get("shift_instance"),
                worksite_id=worksite_id,
            )
        except Exception as exc:
            raise DRFValidationError({"detail": str(exc)})

        return Response(AttendanceEventSerializer(ev).data, status=status.HTTP_201_CREATED)


# --- Check Out ---
@extend_schema_view(
    post=extend_schema(
        tags=["Attendance"],
        summary="Check out",
        description=(
            "Chỉ cho phép khi có X-Local-Access (JWT được cấp sau khi Agent LAN xác thực). "
            "Server tự gán thời điểm check-out = thời gian hiện tại (timezone-aware)."
        ),
        request=AttendanceCheckSerializer,
        responses={
            200: OpenApiResponse(AttendanceEventSerializer, description="Cập nhật sự kiện check-out"),
            **std_errors(),
        },
        examples=[
            OpenApiExample(
                "Body mẫu (ts bỏ qua / không cần gửi)",
                request_only=True,
                value={
                    "employee": 1,
                    "lat": 10.77,
                    "lng": 106.69,
                    "accuracy_m": 9.8,
                    "worksite": 3,
                    "shift_instance": 12,
                    "source": "web",
                },
            ),
        ],
    )
)
class CheckOutView(APIView):
    def post(self, request):
        # 1) BẮT BUỘC: xác thực LAN qua local_access_token trong header
        local_token = request.headers.get("X-Local-Access")
        try:
            claims = require_local_access_token(local_token)
        except Exception as exc:
            raise DRFValidationError({"detail": str(exc)})

        # 2) Parse input như cũ
        ser = AttendanceCheckSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        emp = _get_active_employee(v["employee"])
        now = timezone.now()

        agent_code = claims.get("agent_code")
        # worksite_id = map_agent_to_worksite_id(agent_code)
        worksite_id = v.get("worksite")

        try:
            ev = add_check_out(
                employee=emp,
                ts=now,
                lat=v.get("lat"),
                lng=v.get("lng"),
                accuracy_m=v.get("accuracy_m"),
                source=v.get("source") or "web",
                shift_instance_id=v.get("shift_instance"),
                worksite_id=worksite_id,
            )
        except Exception as exc:
            raise DRFValidationError({"detail": str(exc)})

        return Response(AttendanceEventSerializer(ev).data, status=status.HTTP_200_OK)


# --- Summary by day ---
@extend_schema_view(
    get=extend_schema(
        tags=["Attendance"],
        summary="Attendance summary theo ngày",
        parameters=[
            q_int("employee", "Employee ID"),
            q_date("date_from", "Từ ngày (YYYY-MM-DD)"),
            q_date("date_to", "Đến ngày (YYYY-MM-DD)"),
        ],
        responses=OpenApiResponse(AttendanceSummarySerializer(many=True), description="Danh sách summary"),
    )
)
class AttendanceSummaryView(APIView):
    def get(self, request):
        emp = request.query_params.get("employee")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        qs = AttendanceSummary.objects.select_related("employee").all().order_by("-date", "-id")
        if emp:
            qs = qs.filter(employee_id=emp)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return Response(AttendanceSummarySerializer(qs, many=True).data)
