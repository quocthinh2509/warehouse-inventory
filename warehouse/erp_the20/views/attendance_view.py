from datetime import datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from typing import List, Optional
from django.utils import timezone

from erp_the20.serializers.attendance_serializer import (
    AttendanceEventReadSerializer,
    AttendanceEventWriteSerializer,
    AttendanceSummaryReadSerializer,
    AttendanceSummaryWriteSerializer,
)

from erp_the20.services import attendance_service
from erp_the20.selectors import attendance_selector


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
    def get(self, request):
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

class ListAttendanceEvent(APIView):
    """
    API lấy AttendanceEvent (join User/ShiftInstance/ShiftTemplate)
    Hỗ trợ filter theo: employee_id (1 hoặc nhiều, cách nhau bằng dấu phẩy),
    username, start, end (YYYY-MM-DD), event_type ('in' | 'out').
    """

    def get(self, request):
        # --- Lấy query params ---
        employee_id_param = request.query_params.get("employee_id")  # vd: "12" hoặc "12,13,99"
        username = request.query_params.get("username")
        start = request.query_params.get("start")   # "YYYY-MM-DD"
        end = request.query_params.get("end")       # "YYYY-MM-DD"
        event_type = request.query_params.get("event_type")  # "in" hoặc "out"

        # --- Parse employee_ids ---
        employee_ids = None
        if employee_id_param:
            try:
                employee_ids = [
                    int(x) for x in str(employee_id_param).replace(" ", "").split(",") if x
                ]
            except ValueError:
                return Response(
                    {"error": "employee_id phải là số hoặc danh sách số, ngăn cách bằng dấu phẩy."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # --- Validate event_type ---
        if event_type and event_type not in {"in", "out"}:
            return Response(
                {"error": "event_type chỉ nhận 'in' hoặc 'out'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Parse & validate dates ---
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date() if start else None
            end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else None
        except ValueError:
            return Response(
                {"error": "Ngày không đúng định dạng (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if start_date and end_date and start_date > end_date:
            return Response(
                {"error": "start không thể lớn hơn end."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Gọi selector ---
        rows = attendance_selector.list_attendance_full(
            employee_ids=employee_ids,
            username=username,
            start=start_date,
            end=end_date,
            event_type=event_type
        )

        # --- Serialize RawQuerySet -> list[dict] ---
        data = []
        for r in rows:
            item = {
                # Fields từ AttendanceEvent (eta.*)
                "id": getattr(r, "id", None),
                "employee_id": getattr(r, "employee_id", None),
                "ts": r.ts.isoformat() if getattr(r, "ts", None) else None,
                "event_type": getattr(r, "event_type", None),
                "shift_instance_id": getattr(r, "shift_instance_id", None),

                # Các cột thêm từ JOIN
                "username": getattr(r, "username", None),
                "email": getattr(r, "email", None),
                "shift_date": getattr(r, "shift_date", None).isoformat()
                    if getattr(r, "shift_date", None) is not None else None,
                "shift_status": getattr(r, "shift_status", None),
                "template_code": getattr(r, "template_code", None),
                "template_name": getattr(r, "template_name", None),
                "template_start": str(getattr(r, "template_start", None))
                    if getattr(r, "template_start", None) else None,
                "template_end": str(getattr(r, "template_end", None))
                    if getattr(r, "template_end", None) else None,
                "break_minutes": getattr(r, "break_minutes", None),
                "overnight": getattr(r, "overnight", None),
            }
            data.append(item)

        return Response(
            {"count": len(data), "results": data},
            status=status.HTTP_200_OK
        )
    


class GetLastEvent(APIView):
    """
    API lấy sự kiện chấm công gần nhất của nhân viên
    Query params:
        ?employee=101
    """

    def get(self, request):
        employee = request.query_params.get("employee")

        if not employee:
            return Response({"error": "employee is required"}, status=status.HTTP_400_BAD_REQUEST)

        ev = attendance_selector.get_last_attendance_event_by_date(int(employee), timezone.localdate())
        if not ev:
            return Response({"detail": "No events found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AttendanceEventReadSerializer(ev)
        return Response(serializer.data, status=status.HTTP_200_OK)
    



class TodaySummaryView(APIView):
    """
    GET /api/attendance/summary/today?employee=101

    - FE chỉ truyền employee id.
    - Server tự lấy ngày hôm nay theo timezone của Django (timezone.localdate()).
    - Luôn gọi build_daily_summary để đảm bảo dữ liệu mới nhất rồi trả về summary.
    """
    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        employee = request.query_params.get("employee")
        if not employee:
            return Response({"error": "employee is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            employee_id = int(employee)
        except (TypeError, ValueError):
            return Response({"error": "employee must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Không truyền date => service tự dùng timezone.localdate()
            summary = attendance_service.build_daily_summary(employee_id)
            data = AttendanceSummaryReadSerializer(summary).data
            # Thêm thông tin ngày server để FE debug nếu cần
            #data["_server_date"] = timezone.localdate().isoformat()
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "failed_to_build_summary", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RebuildSummariesTodayView(APIView):
    """
    POST /api/attendance/summary/rebuild-today
    Body (tùy chọn):
    {
      "employee_ids": [101, 102, 103]   # nếu bỏ trống: rebuild tất cả NV có event/leave hôm nay
    }

    - Server tự lấy ngày hôm nay.
    - Dùng rebuild_summaries_for_date(...) => trả về số lượng summary đã rebuild.
    """
    # permission_classes = [permissions.IsAuthenticated]  # Có thể siết chặt: [permissions.IsAdminUser]

    def post(self, request):
        employee_ids: Optional[List[int]] = request.data.get("employee_ids")

        if employee_ids is not None and not isinstance(employee_ids, list):
            return Response(
                {"error": "employee_ids must be a list of integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if isinstance(employee_ids, list):
            # Validate list phần tử phải là int
            try:
                employee_ids = [int(x) for x in employee_ids]
            except (TypeError, ValueError):
                return Response(
                    {"error": "employee_ids elements must be integers"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            rebuilt_count = attendance_service.rebuild_summaries_for_date(employee_ids=employee_ids)
            return Response(
                {
                    "date": timezone.localdate().isoformat(),
                    "rebuilt": rebuilt_count,
                    "filtered_by_employee_ids": bool(employee_ids),
                    "employee_ids": employee_ids or [],
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "failed_to_rebuild_summaries", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )