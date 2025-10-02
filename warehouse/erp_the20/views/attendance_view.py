from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter

from django.utils import timezone

from erp_the20.serializers.attendance_serializer import (
    AttendanceEventReadSerializer,
    AttendanceEventWriteSerializer,
    AttendanceSummaryReadSerializer,
    AttendanceSummaryWriteSerializer,
)

from erp_the20.services import attendance_service
from erp_the20.selectors import attendance_selector


# =========================
# Attendance Events
# =========================

class AttendanceCheckInView(APIView):
    """
    API để nhân viên check-in
    Body:
    {
        "employee": 101,
        "valid": true,
        "source": "mobile",
        "shift_instance": 1  (optional)
    }
    """

    def post(self, request):
        employee = request.data.get("employee")
        valid = request.data.get("valid", True)
        source = request.data.get("source", "unknown")
        shift_instance_id = request.data.get("shift_instance")

        if not employee:
            return Response({"error": "employee is required"}, status=status.HTTP_400_BAD_REQUEST)

        ev = attendance_service.add_check_in(
            employee=employee,
            valid=valid,
            source=source,
            shift_instance_id=shift_instance_id,
        )
        serializer = AttendanceEventReadSerializer(ev)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AttendanceCheckOutView(APIView):
    """
    API để nhân viên check-out
    Body:
    {
        "employee": 101,
        "valid": true,
        "source": "mobile",
        "shift_instance": 1  (optional)
    }
    """

    def post(self, request):
        employee = request.data.get("employee")
        valid = request.data.get("valid", True)
        source = request.data.get("source", "unknown")
        shift_instance_id = request.data.get("shift_instance")

        if not employee:
            return Response({"error": "employee is required"}, status=status.HTTP_400_BAD_REQUEST)

        ev = attendance_service.add_check_out(
            employee=employee,
            valid=valid,
            source=source,
            shift_instance_id=shift_instance_id,
        )
        serializer = AttendanceEventReadSerializer(ev)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AttendanceEventListView(APIView):
    """
    API list attendance events (filter theo employee, date range)
    Query params:
        ?employee=101&start=2025-10-01&end=2025-10-02
    """

    def get(self, request):
        employee_ids = request.query_params.getlist("employee")
        start = request.query_params.get("start")
        end = request.query_params.get("end")

        qs = attendance_selector.list_attendance_events(
            employee_ids=[int(e) for e in employee_ids] if employee_ids else None,
            start=start,
            end=end,
        )
        serializer = AttendanceEventReadSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =========================
# Attendance Summaries
# =========================

class AttendanceSummaryListView(APIView):
    """
    API list summaries
    Query:
        ?employee=101
        ?date=2025-10-02
    """

    def get(self, request):
        employee = request.query_params.get("employee")
        date_str = request.query_params.get("date")

        if employee and date_str:
            summary = attendance_selector.get_summary(int(employee), date_str)
            if not summary:
                return Response([], status=status.HTTP_200_OK)
            serializer = AttendanceSummaryReadSerializer(summary)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif employee:
            summaries = attendance_selector.list_summaries(int(employee))
            serializer = AttendanceSummaryReadSerializer(summaries, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif date_str:
            summaries = attendance_selector.list_summaries_by_date(date_str)
            serializer = AttendanceSummaryReadSerializer(summaries, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        else:
            summaries = attendance_selector.list_all_summaries()
            serializer = AttendanceSummaryReadSerializer(summaries, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)


class AttendanceEventListByDateView(APIView):
    """
    API list attendance events của nhân viên theo ngày
    Query params:
        ?employee=101&date=2025-10-02
    """

    def get(self, request):
        employee = request.query_params.get("employee_id")
        date_str = request.query_params.get("date")

        if not employee or not date_str:
            return Response({"error": "employee and date are required"}, status=status.HTTP_400_BAD_REQUEST)

        events = attendance_selector.get_list_event_by_date(int(employee), date_str)
        serializer = AttendanceEventReadSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AttendanceEventListByDatesView(APIView):
    def get(seft,request):
        """
        API list attendance events của nhân viên theo nhiều ngày
        Query params:
            ?employee=101&dates=2025-10-02,2025-10-03
        """
        employee = request.query_params.get("employee_id")
        start_str = request.query_params.get("start")
        end_str = request.query_params.get("end")
        if not employee or not start_str or not end_str:
            return Response({"error": "employee, start and end are required"}, status=status.HTTP_400_BAD_REQUEST)
        events = attendance_selector.list_attendance_events(employee_ids=[int(employee)], start=start_str, end=end_str)
        serializer = AttendanceEventReadSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AttendanceStatsView(APIView):
    """
    API thống kê:
    - currently_clocked_in: số nhân viên đang trong ca (đã checkin, chưa checkout)
    - late: số nhân viên đi trễ
    - on_time: số nhân viên đi đúng giờ
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="date",
                type=str,
                description="Ngày (YYYY-MM-DD). Nếu bỏ trống thì lấy ngày hôm nay",
                required=False,
            )
        ],
        description="Thống kê số nhân viên đi trễ, đúng giờ, đang trong ca."
    )
    def get(self, request):
        # --- Lấy và validate tham số ngày ---
        date_str = request.query_params.get("date")
        if date_str:
            try:
                today = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date format, should be YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            today = timezone.localdate()

        # --- Lấy dữ liệu thống kê ---
        try:
            currently_in = attendance_selector.count_currently_clocked_in()
            late, on_time = attendance_selector.count_late_and_ontime(today)
        except Exception as e:
            return Response(
                {"detail": f"Internal error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # --- Kết quả ---
        data = {
            "date": str(today),
            "currently_clocked_in": currently_in,
            "late": late,
            "on_time": on_time,
        }
        return Response(data, status=status.HTTP_200_OK)