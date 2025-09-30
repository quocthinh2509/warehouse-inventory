# # attendance_view.py
# from rest_framework.views import APIView
# from rest_framework import generics, permissions
# from rest_framework.response import Response
# from django.utils.dateparse import parse_date

# from rest_framework import status
# from rest_framework.exceptions import ValidationError as DRFValidationError, AuthenticationFailed
# from django.core.cache import cache

# import time
# from django.utils.decorators import method_decorator
# from django.views.decorators.csrf import csrf_exempt
# from django.conf import settings
# import traceback
# from datetime import datetime, timedelta

# from erp_the20.models import Employee, AttendanceSummary
# from erp_the20.services.attendance_service import add_check_in, add_check_out
# from erp_the20.serializers.attendance_serializer import (
#     AttendanceEventWriteSerializer,
#     AttendanceEventReadSerializer,
#     AttendanceSummaryReadSerializer,
# )
# from erp_the20.serializers.employee_serializer import EmployeeReadSerializer
# from erp_the20.selectors.employee_selector import get_employee_by_id, get_employee_by_code, get_employee_by_user_name
# from erp_the20.selectors.attendance_selector import (
#     get_last_event, # sự kiện chấm công mới nhất của nhân viên
#     get_summary, # bảng tổng hợp công cho nhân viên theo ngày 
#     list_summaries, # tất cả bảng tổng hợp của nhân viên
#     list_all_summaries, # Lấy toàn bộ bảng tổng hợp công của tất cả nhân viên
#     list_summaries_by_date, # Lấy tất cả bảng tổng hợp công cho một ngày cụ thể
#     get_list_event_by_date, #Lấy danh sách sự kiện chấm công của nhân viên theo ngày
#     list_attendance_events,
# )
# from drf_spectacular.utils import (
#     extend_schema,
#     extend_schema_view,
#     OpenApiResponse,
#     OpenApiParameter,
#     OpenApiExample,
# )

# # ==============================================================
# # Helper
# # ==============================================================
# def _get_active_employee(emp_id: int):
#     try:
#         """Lấy Employee đang active theo ID."""
#         emp = Employee.objects.filter(id=emp_id, is_active=True).first()
#         if not emp:
#             raise DRFValidationError({"employee": "Employee not found or inactive."})
#         return emp
#     except Employee.DoesNotExist:
#         raise DRFValidationError({"employee": "Employee not found."})


# def verify_local_token(request):
#     """
#     Xác thực token X-Local-Access từ agent nội bộ.
#     """
#     token = request.headers.get("X-Local-Access")
#     print("Token",token)
#     if not token:
#         raise AuthenticationFailed("Missing X-Local-Access token")

#     data = cache.get(f"local_token:{token}")
#     print("Data",data)
#     if not data:
#         raise AuthenticationFailed("Invalid or expired local access token")

#     return data


# # ==============================================================
# # Nhận token từ agent
# # ==============================================================
# @extend_schema_view(
#     post=extend_schema(
#         tags=["Attendance"],
#         summary="Nhận local token từ agent",
#         request={
#             "application/json": {
#                 "type": "object",
#                 "properties": {
#                     "token": {"type": "string"},
#                     "issuedAt": {"type": "integer", "example": 1727096400},
#                     "expiresAt": {"type": "integer", "example": 1727098200},
#                     "meta": {"type": "object"},
#                 },
#                 "required": ["token", "expiresAt"],
#             }
#         },
#         responses={
#             201: OpenApiResponse(
#                 response={
#                     "type": "object",
#                     "properties": {
#                         "status": {"type": "string"},
#                         "token": {"type": "string"},
#                         "ttl": {"type": "integer"},
#                     },
#                 },
#                 description="Lưu token thành công",
#             ),
#             400: OpenApiResponse(description="Thiếu hoặc token hết hạn"),
#         },
#     )
# )
# class ReceiveLocalTokenView(APIView):
#     def post(self, request):
#         token = request.data.get("token")
#         expires_at = request.data.get("expiresAt")
#         meta = request.data.get("meta") or {}

#         if not token or not expires_at:
#             return Response({"error": "missing_token"}, status=status.HTTP_400_BAD_REQUEST)

#         ttl = int(expires_at) - int(time.time())
#         if ttl <= 0:
#             return Response({"error": "expired_token"}, status=status.HTTP_400_BAD_REQUEST)

#         cache.set(f"local_token:{token}", meta, timeout=ttl)
#         print(f"[DEBUG] save token={token} ttl={ttl} backend={cache.__class__}")
#         return Response({"status": "ok", "token": token, "ttl": ttl}, status=status.HTTP_201_CREATED)


# # ==============================================================
# # Check-in
# # ==============================================================
# @extend_schema_view(
#     post=extend_schema(
#         tags=["Attendance"],
#         summary="Check in",
#         description="Chỉ cho phép khi có X-Local-Access header.",
#         request=AttendanceEventWriteSerializer,
#         responses={201: OpenApiResponse(AttendanceEventReadSerializer)},
#         examples=[
#             OpenApiExample(
#                 "Body mẫu",
#                 request_only=True,
#                 value={"employee": 1, "shift_instance": 12, "source": "web"},
#             )
#         ],
#     )
# )


# class CheckInView(APIView):
#     def post(self, request):
#         try:
#             claims = verify_local_token(request)

#             serializer = AttendanceEventWriteSerializer(data=request.data, partial=True)
#             serializer.is_valid(raise_exception=True)
#             data = serializer.validated_data

#             employee = _get_active_employee(data["employee"].id)

#             event = add_check_in(
#                 employee=employee,
#                 valid=claims,
#                 source=data.get("source", "web"),
#                 shift_instance_id=data["shift_instance"].id if data.get("shift_instance") else None,
#             )

#             return Response(
#                 AttendanceEventReadSerializer(event).data,
#                 status=status.HTTP_201_CREATED,
#             )
#         except Exception as exc:
#             print("❌ Exception in CheckInView:", exc)
#             traceback.print_exc()
#             raise DRFValidationError({"detail": str(exc)})

# # ==============================================================
# # Check-out
# # ==============================================================
# @extend_schema_view(
#     post=extend_schema(
#         tags=["Attendance"],
#         summary="Check out",
#         description="Chỉ cho phép khi có X-Local-Access header.",
#         request=AttendanceEventWriteSerializer,
#         responses={200: OpenApiResponse(AttendanceEventReadSerializer)},
#     )
# )
# class CheckOutView(APIView):
#     def post(self, request):
#         try:
#             claims = verify_local_token(request)

#             serializer = AttendanceEventWriteSerializer(data=request.data, partial=True)
#             serializer.is_valid(raise_exception=True)
#             data = serializer.validated_data

#             employee = _get_active_employee(data["employee"].id)

#             event = add_check_out(
#                 employee=employee,
#                 valid=claims,
#                 source=data.get("source", "web"),
#                 shift_instance_id=data["shift_instance"].id if data.get("shift_instance") else None,
#             )

#             return Response(
#                 AttendanceEventReadSerializer(event).data,
#                 status=status.HTTP_201_CREATED,
#             )
#         except Exception as exc:
#             print("❌ Exception in CheckInView:", exc)
#             traceback.print_exc()
#             raise DRFValidationError({"detail": str(exc)})


# # ==============================================================
# # AttendanceSummary listing
# # ==============================================================
# @extend_schema_view(
#     get=extend_schema(
#         tags=["Attendance"],
#         summary="Danh sách Attendance Summary",
#         parameters=[
#             OpenApiParameter("employee", int, OpenApiParameter.QUERY, description="Employee ID"),
#             OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="Từ ngày (YYYY-MM-DD)"),
#             OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="Đến ngày (YYYY-MM-DD)"),
#         ],
#         responses=OpenApiResponse(AttendanceSummaryReadSerializer(many=True)),
#     )
# )
# class AttendanceSummaryView(APIView):
#     def get(self, request):
#         emp = request.query_params.get("employee")
#         date_from = request.query_params.get("date_from")
#         date_to = request.query_params.get("date_to")

#         qs = AttendanceSummary.objects.select_related("employee").all().order_by("-date", "-id")
#         if emp:
#             qs = qs.filter(employee_id=emp)
#         if date_from:
#             qs = qs.filter(date__gte=date_from)
#         if date_to:
#             qs = qs.filter(date__lte=date_to)

#         return Response(AttendanceSummaryReadSerializer(qs, many=True).data)


# @extend_schema_view(
#     get=extend_schema(
#         tags=["Attendance"],
#         summary="Xem toàn bộ local token trong cache (debug)",
#         responses={200: OpenApiResponse(
#             response={
#                 "type": "object",
#                 "additionalProperties": {"type": "object"},
#             },
#             description="Danh sách token đang lưu"
#         )}
#     )
# )
# @method_decorator(csrf_exempt, name="dispatch")
# class DebugTokenListView(APIView):
#     def get(self, request):
#         """
#         Liệt kê toàn bộ key local_token:* đang có trong cache.
#         Chỉ nên bật khi DEBUG = True.
#         """
#         if not settings.DEBUG:
#             return Response({"error": "Disabled in production"}, status=status.HTTP_403_FORBIDDEN)

#         tokens = {}
#         # Nếu dùng LocMemCache:
#         try:
#             for key in cache._cache.keys():  # LocMemCache
#                 if key.startswith("local_token:"):
#                     tokens[key] = cache.get(key)
#         except AttributeError:
#             # Nếu Redis/ Memcached không có ._cache, cần config redis scan/keys
#             return Response({"error": "Listing not supported for this cache backend"},
#                             status=status.HTTP_501_NOT_IMPLEMENTED)

#         return Response(tokens, status=status.HTTP_200_OK)



# class AttendanceEventListView(generics.ListAPIView):
#     """
#     GET /api/attendance/events/?employee_ids=1,2&start=2024-09-01&end=2024-09-30
#     """
#     serializer_class = AttendanceEventReadSerializer
#     # permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         ids_param = self.request.query_params.get("employee_ids")
#         employee_ids = [int(i) for i in ids_param.split(",")] if ids_param else None

#         start = parse_date(self.request.query_params.get("start") or "")
#         end   = parse_date(self.request.query_params.get("end") or "")

#         # 👉 chỉ điều phối: gọi selector
#         return list_attendance_events(employee_ids=employee_ids, start=start, end=end)

# attendance_view.py
import time
import traceback
import logging
from datetime import datetime

from django.utils.dateparse import parse_date
from django.core.cache import cache
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError, AuthenticationFailed

from erp_the20.models import Employee, AttendanceSummary
from erp_the20.services.attendance_service import add_check_in, add_check_out
from erp_the20.serializers.attendance_serializer import (
    AttendanceEventWriteSerializer,
    AttendanceEventReadSerializer,
    AttendanceSummaryReadSerializer,
)
from erp_the20.selectors.attendance_selector import list_attendance_events

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiParameter,
    OpenApiExample,
)

logger = logging.getLogger(__name__)

# ==============================================================
# Helper
# ==============================================================
def _get_active_employee(emp_id: int):
    emp = Employee.objects.filter(id=emp_id, is_active=True).first()
    if not emp:
        logger.warning(f"[Attendance] Employee {emp_id} not found or inactive")
        raise DRFValidationError({"employee": "Employee not found or inactive."})
    return emp


def verify_local_token(request):
    token = request.headers.get("X-Local-Access")
    if not token:
        logger.error("[Attendance] ❌ Missing X-Local-Access header")
        raise AuthenticationFailed("Missing X-Local-Access token")

    cache_key = f"local_token:{token}"
    data = cache.get(cache_key)

    if not data:
        logger.error(f"[Attendance] ❌ Token invalid or expired: {token}")
        raise AuthenticationFailed("Invalid or expired local access token")

    now = int(time.time())
    exp = data.get("expires_at")
    ttl_remaining = exp - now if exp else None

    logger.info(
        f"[Attendance] 🔑 Verify token OK: {token[:12]}... "
        f"TTL_remaining={ttl_remaining}s, meta={data.get('meta')}"
    )

    return data



# ==============================================================
# Nhận token từ agent
# ==============================================================
@extend_schema_view(
    post=extend_schema(
        tags=["Attendance"],
        summary="Nhận local token từ agent",
    )
)
class ReceiveLocalTokenView(APIView):
    """
    Nhận token từ Flask, lưu cache và trả về kết quả kiểm tra
    """

    def post(self, request):
        try:
            token = request.data.get("token")
            expires_at = request.data.get("expiresAt")
            meta = request.data.get("meta") or {}

            if not token or not expires_at:
                logger.error("[Attendance] ❌ Missing token hoặc expiresAt")
                return Response({"error": "missing_token_or_expiresAt"},
                                status=status.HTTP_400_BAD_REQUEST)

            now = int(time.time())
            ttl = int(expires_at) - now
            if ttl <= 0:
                logger.warning(f"[Attendance] ⚠️ Received expired token: {token}")
                return Response({"error": "expired_token", "now": now, "expires_at": expires_at},
                                status=status.HTTP_400_BAD_REQUEST)

            # 1️⃣ Lưu vào cache
            cache_key = f"local_token:{token}"
            cache.set(cache_key, {"meta": meta, "expires_at": int(expires_at)}, timeout=ttl)

            logger.info(f"[Attendance] ✅ Token saved: {token}, TTL={ttl}s (exp={expires_at})")

            # 2️⃣ Kiểm tra lại ngay sau khi set
            cached_value = cache.get(cache_key)

            if not cached_value:
                logger.error(f"[Attendance] ❌ Token {token} KHÔNG lưu được vào cache")
                return Response({
                    "status": "fail",
                    "reason": "cache_set_failed",
                    "token": token,
                    "expires_at": expires_at,
                    "ttl": ttl
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 3️⃣ Trả về chi tiết
            return Response({
                "status": "ok",
                "saved_token": token,
                "expires_at": int(expires_at),
                "ttl": ttl,
                "cached_value": cached_value,
                "now": now,
                "debug_note": "Token đã được lưu trong cache, nếu vẫn lỗi khi checkin/checkout thì có thể do frontend không gửi đúng header X-Local-Access hoặc token đã hết hạn."
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"[Attendance] ❌ Exception khi lưu token: {e}")
            traceback.print_exc()
            return Response({
                "error": "server_error",
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================================================
# Check-in
# ==============================================================
@extend_schema_view(
    post=extend_schema(
        tags=["Attendance"],
        summary="Check in",
    )
)
class CheckInView(APIView):
    def post(self, request):
        try:
            token = request.headers.get("X-Local-Access")
            logger.debug(f"[Attendance] 📨 CheckIn request với token={token}")

            claims = verify_local_token(request)
            serializer = AttendanceEventWriteSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            employee = _get_active_employee(data["employee"].id)
            event = add_check_in(
                employee=employee,
                valid=claims,
                source=data.get("source", "web"),
                shift_instance_id=data["shift_instance"].id if data.get("shift_instance") else None,
            )

            logger.info(f"[Attendance] 🎉 CHECKIN thành công cho employee={employee.id}, token OK")
            return Response(AttendanceEventReadSerializer(event).data, status=status.HTTP_201_CREATED)

        except Exception as exc:
            logger.error(f"[Attendance] ⚠️ Checkin failed: {exc}")
            traceback.print_exc()
            raise DRFValidationError({"detail": str(exc)})

# ==============================================================
# Check-out
# ==============================================================
@extend_schema_view(
    post=extend_schema(
        tags=["Attendance"],
        summary="Check out",
    )
)
class CheckOutView(APIView):
    def post(self, request):
        try:
            token = request.headers.get("X-Local-Access")
            logger.debug(f"[Attendance] 📨 CheckOut request với token={token}")

            claims = verify_local_token(request)
            serializer = AttendanceEventWriteSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            employee = _get_active_employee(data["employee"].id)
            event = add_check_out(
                employee=employee,
                valid=claims,
                source=data.get("source", "web"),
                shift_instance_id=data["shift_instance"].id if data.get("shift_instance") else None,
            )

            logger.info(f"[Attendance] 🎉 CHECKOUT thành công cho employee={employee.id}, token OK")
            return Response(AttendanceEventReadSerializer(event).data, status=status.HTTP_201_CREATED)

        except Exception as exc:
            logger.error(f"[Attendance] ⚠️ Checkout failed: {exc}")
            traceback.print_exc()
            raise DRFValidationError({"detail": str(exc)})


# ==============================================================
# AttendanceSummary listing
# ==============================================================
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

        return Response(AttendanceSummaryReadSerializer(qs, many=True).data)


# ==============================================================
# Debug token (chỉ khi DEBUG=True)
# ==============================================================
@method_decorator(csrf_exempt, name="dispatch")
class DebugTokenListView(APIView):
    def get(self, request):
        if not settings.DEBUG:
            return Response({"error": "Disabled in production"}, status=status.HTTP_403_FORBIDDEN)

        tokens = {}
        now = int(time.time())
        try:
            for key in cache._cache.keys():
                if key.startswith("local_token:"):
                    val = cache.get(key)
                    if val:
                        exp = val.get("expires_at")
                        tokens[key] = {
                            "meta": val.get("meta"),
                            "expires_at": exp,
                            "ttl_remaining": int(exp) - now if exp else None,
                        }
        except AttributeError:
            return Response({"error": "Listing not supported for this cache backend"},
                            status=status.HTTP_501_NOT_IMPLEMENTED)

        logger.info(f"[Attendance] 📌 Debug tokens: {tokens}")
        return Response(tokens, status=status.HTTP_200_OK)


# ==============================================================
# Danh sách sự kiện AttendanceEvent
# ==============================================================
class AttendanceEventListView(generics.ListAPIView):
    serializer_class = AttendanceEventReadSerializer

    def get_queryset(self):
        ids_param = self.request.query_params.get("employee_ids")
        employee_ids = [int(i) for i in ids_param.split(",")] if ids_param else None

        start = parse_date(self.request.query_params.get("start") or "")
        end = parse_date(self.request.query_params.get("end") or "")

        return list_attendance_events(employee_ids=employee_ids, start=start, end=end)
