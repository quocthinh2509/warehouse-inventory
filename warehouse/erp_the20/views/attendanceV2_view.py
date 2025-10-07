# erp_the20/views/attendanceV2_view.py
from __future__ import annotations
from typing import Dict, Any, List

from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiExample, OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from erp_the20.models import AttendanceSummaryV2
from erp_the20.serializers.attendanceV2_serializer import (
    AttendanceSummaryV2ReadSerializer,
    RegisterShiftSerializer,
    UpdateRegistrationSerializer,
    CancelRegistrationSerializer,
    ManagerCancelSerializer,
    ApproveDecisionSerializer,
    SearchFiltersSerializer,
    BulkRegisterSerializer,
)
from erp_the20.services.attendanceV2_service import (
    register_shift as svc_register_shift,
    update_registration as svc_update_registration,
    delete_registration as svc_delete_registration,
    cancel_registration as svc_cancel_registration,
    approve_summary as svc_approve_summary,
    reject_summary as svc_reject_summary,
    manager_cancel_summary as svc_manager_cancel_summary,
    register_shifts_bulk_for_next_week,
)
from erp_the20.selectors.attendanceV2_selector import (
    list_my_pending,
    list_pending_for_manager,
    filter_summaries,
)
from erp_the20.selectors.user_selector import is_employee_manager


# ---- helpers (giữ nguyên) ----
def _qp_get_multi(request, key: str) -> List[str]:
    vs = request.query_params.getlist(key)
    if not vs:
        raw = request.query_params.get(key)
        if raw:
            vs = [x for x in raw.split(",") if x != ""]
    out = []
    for v in vs:
        s = str(v).strip()
        if s:
            out.append(s)
    return out

def _build_search_filters(request) -> Dict[str, Any]:
    return {
        "employee_id": _qp_get_multi(request, "employee_id") or request.query_params.get("employee_id"),
        "status": _qp_get_multi(request, "status") or request.query_params.get("status"),
        "is_valid": request.query_params.get("is_valid"),
        "work_mode": _qp_get_multi(request, "work_mode") or request.query_params.get("work_mode"),
        "source": _qp_get_multi(request, "source") or request.query_params.get("source"),
        "template_code": _qp_get_multi(request, "template_code") or request.query_params.get("template_code"),
        "template_name_icontains": request.query_params.get("template_name"),
        "approved_by": _qp_get_multi(request, "approved_by") or request.query_params.get("approved_by"),
        "requested_by": _qp_get_multi(request, "requested_by") or request.query_params.get("requested_by"),
        "shift_date_from": request.query_params.get("from") or request.query_params.get("shift_date_from"),
        "shift_date_to": request.query_params.get("to") or request.query_params.get("shift_date_to"),
        "ts_in_from": request.query_params.get("ts_in_from"),
        "ts_in_to": request.query_params.get("ts_in_to"),
        "ts_out_from": request.query_params.get("ts_out_from"),
        "ts_out_to": request.query_params.get("ts_out_to"),
        "bonus_min": request.query_params.get("bonus_min"),
        "bonus_max": request.query_params.get("bonus_max"),
        "q": request.query_params.get("q"),
    }




@extend_schema_view(
    create=extend_schema(
        tags=["Attendance V2"],
        summary="Nhân viên đăng ký ca",
        description="Tạo bản đăng ký ca mới. Chỉ cho phép Thứ 5→Thứ 7 đối với nhân viên thường.",
        request=RegisterShiftSerializer,
        responses={
            201: AttendanceSummaryV2ReadSerializer,
            400: OpenApiResponse(description="Bad request / Overlap / Validation error"),
            403: OpenApiResponse(description="Không trong khung ngày cho phép"),
        },
        examples=[
            OpenApiExample(
                "Register shift",
                value={"employee_id": 204, "shift_instance_id": 5},
                request_only=True
            )
        ],
    ),
    update=extend_schema(
        tags=["Attendance V2"],
        summary="Cập nhật đăng ký (đổi ca)",
        request=UpdateRegistrationSerializer,
        responses={200: AttendanceSummaryV2ReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
        examples=[OpenApiExample("Update", value={
            "employee_id": 204, "new_shift_instance_id": 7, "requested_by": 204
        }, request_only=True)],
    ),
    destroy=extend_schema(
        tags=["Attendance V2"],
        summary="Xoá đăng ký",
        parameters=[
            OpenApiParameter("employee_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=True,
                             description="Employee thực hiện xoá"),
        ],
        responses={204: OpenApiResponse(description="Deleted"), 400: OpenApiResponse(), 403: OpenApiResponse()},
    ),
)
class AttendanceSummaryV2ViewSet(
    viewsets.GenericViewSet,
    mixins.DestroyModelMixin,
):
    """
    RESTful endpoints:
      - POST   /attendanceV2/summary-v2/
      - PUT    /attendanceV2/summary-v2/{id}/
      - PUT    /attendanceV2/summary-v2/{id}/cancel/
      - PUT    /attendanceV2/summary-v2/{id}/approve/
      - PUT    /attendanceV2/summary-v2/{id}/manager-cancel/
      - DELETE /attendanceV2/summary-v2/{id}/
      - GET    /attendanceV2/summary-v2/my-pending?employee_id=...
      - GET    /attendanceV2/summary-v2/pending?from=...&to=...&manager_id=...
      - GET    /attendanceV2/summary-v2/search?...
    """
    queryset = AttendanceSummaryV2.objects.all()
    serializer_class = AttendanceSummaryV2ReadSerializer
    permission_classes = [permissions.AllowAny]

    # ===== Create (POST /) =====
    def create(self, request):
        ser = RegisterShiftSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        employee_id = ser.validated_data["employee_id"]
        actor_is_mgr = is_employee_manager(employee_id)

        try:
            obj = svc_register_shift(
                employee_id=employee_id,
                shift_instance_id=ser.validated_data["shift_instance_id"],
                requested_by=employee_id,
                actor_is_manager=actor_is_mgr,
                
            )
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(AttendanceSummaryV2ReadSerializer(obj).data, status=201)


    # ===== Update (PUT /{id}/) =====
    def update(self, request, pk=None):
        payload = dict(request.data)
        payload["summary_id"] = pk
        ser = UpdateRegistrationSerializer(data=payload)
        ser.is_valid(raise_exception=True)

        actor_is_mgr = is_employee_manager(ser.validated_data["employee_id"])

        try:
            obj = svc_update_registration(
                employee_id=ser.validated_data["employee_id"],
                summary_id=int(pk),
                new_shift_instance_id=ser.validated_data["new_shift_instance_id"],
                requested_by=ser.validated_data.get("requested_by"),
                actor_is_manager=actor_is_mgr,
            )
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(AttendanceSummaryV2ReadSerializer(obj).data)

    # ===== Delete (DELETE /{id}/) =====
    def destroy(self, request, pk=None):
        employee_id = request.query_params.get("employee_id") or request.data.get("employee_id")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response({"detail": "Missing/invalid employee_id in request."}, status=400)

        get_object_or_404(AttendanceSummaryV2, id=pk)
        actor_is_mgr = is_employee_manager(employee_id)

        try:
            svc_delete_registration(
                employee_id=employee_id,
                summary_id=int(pk),
                actor_is_manager=actor_is_mgr,
            )
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(status=204)

    # ===== Cancel (PUT /{id}/cancel/) =====
    @extend_schema(
        tags=["Attendance V2"],
        summary="Nhân viên huỷ đăng ký",
        request=CancelRegistrationSerializer,
        responses={200: AttendanceSummaryV2ReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
        examples=[OpenApiExample("Cancel", value={"employee_id": 204}, request_only=True)],
    )
    @action(detail=True, methods=["put"], url_path="cancel")
    def cancel(self, request, pk=None):
        payload = dict(request.data)
        payload["summary_id"] = pk
        ser = CancelRegistrationSerializer(data=payload)
        ser.is_valid(raise_exception=True)

        actor_is_mgr = is_employee_manager(ser.validated_data["employee_id"])

        try:
            obj = svc_cancel_registration(
                actor_user_id=ser.validated_data["employee_id"],
                summary_id=int(pk),
                actor_is_manager=actor_is_mgr,
            )
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(AttendanceSummaryV2ReadSerializer(obj).data)

    # ===== Approve/Reject (PUT /{id}/approve/) =====
    @extend_schema(
        tags=["Attendance V2"],
        summary="Quản lý duyệt / từ chối",
        request=ApproveDecisionSerializer,
        responses={200: AttendanceSummaryV2ReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
        examples=[
            OpenApiExample("Approve", value={"manager_id": 1, "approve": True, "override_overlap": False}, request_only=True),
            OpenApiExample("Reject",  value={"manager_id": 1, "approve": False, "reason": "Thiếu năng lực đối ứng"}, request_only=True),
        ],
    )
    @action(detail=True, methods=["put"], url_path="approve")
    def approve_or_reject(self, request, pk=None):
        payload = dict(request.data)
        payload["summary_id"] = pk
        ser = ApproveDecisionSerializer(data=payload)
        ser.is_valid(raise_exception=True)

        sid = int(pk)
        approve = ser.validated_data["approve"]
        reason = ser.validated_data.get("reason") or ""
        override = bool(ser.validated_data.get("override_overlap", False))

        manager_id = ser.validated_data.get("manager_id")
        if manager_id is None:
            return Response({"detail": "manager_id is required."}, status=400)
        if not is_employee_manager(manager_id):
            return Response({"detail": "Manager privilege required."}, status=403)

        get_object_or_404(AttendanceSummaryV2, id=sid)
        try:
            if approve:
                obj = svc_approve_summary(manager_user_id=manager_id, summary_id=sid, override_overlap=override)
            else:
                obj = svc_reject_summary(manager_user_id=manager_id, summary_id=sid, reason=reason)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(AttendanceSummaryV2ReadSerializer(obj).data)

    # ===== Manager cancel (PUT /{id}/manager-cancel/) =====
    @extend_schema(
        tags=["Attendance V2"],
        summary="Quản lý huỷ bản đăng ký",
        request=ManagerCancelSerializer,
        responses={200: AttendanceSummaryV2ReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
        examples=[OpenApiExample("Manager cancel", value={"manager_id": 1, "reason": "Đổi lịch công ty"}, request_only=True)],
    )
    @action(detail=True, methods=["put"], url_path="manager-cancel")
    def manager_cancel(self, request, pk=None):
        payload = dict(request.data)
        payload["summary_id"] = pk
        ser = ManagerCancelSerializer(data=payload)
        ser.is_valid(raise_exception=True)

        manager_id = ser.validated_data.get("manager_id")
        if manager_id is None:
            return Response({"detail": "manager_id is required."}, status=400)
        if not is_employee_manager(manager_id):
            return Response({"detail": "Manager privilege required."}, status=403)

        try:
            obj = svc_manager_cancel_summary(
                manager_user_id=manager_id,
                summary_id=int(pk),
                reason=ser.validated_data.get("reason") or "",
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(AttendanceSummaryV2ReadSerializer(obj).data)

    # ===== Reads (GET) =====
    @extend_schema(
        tags=["Attendance V2"],
        summary="Danh sách pending của tôi",
        parameters=[
            OpenApiParameter("employee_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=True),
        ],
        responses={200: AttendanceSummaryV2ReadSerializer(many=True), 400: OpenApiResponse()},
    )
    @action(detail=False, methods=["get"], url_path="my-pending")
    def my_pending(self, request):
        employee_id = request.query_params.get("employee_id")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response({"detail": "Missing/invalid employee_id."}, status=400)

        qs = list_my_pending(employee_id)
        return Response(AttendanceSummaryV2ReadSerializer(qs, many=True).data)

    @extend_schema(
        tags=["Attendance V2"],
        summary="Quản lý xem danh sách pending",
        parameters=[
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("from", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("to", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False, description="YYYY-MM-DD"),
        ],
        responses={200: AttendanceSummaryV2ReadSerializer(many=True), 400: OpenApiResponse(), 403: OpenApiResponse()},
    )
    @action(detail=False, methods=["get"], url_path="pending")
    def manager_pending(self, request):
        manager_id = request.query_params.get("manager_id")
        try:
            manager_id = int(manager_id)
        except (TypeError, ValueError):
            return Response({"detail": "manager_id is required."}, status=400)
        if not is_employee_manager(manager_id):
            return Response({"detail": "Manager privilege required."}, status=403)

        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        qs = list_pending_for_manager(date_from, date_to)
        return Response(AttendanceSummaryV2ReadSerializer(qs, many=True).data)

    @extend_schema(
        tags=["Attendance V2"],
        summary="Tìm kiếm đa điều kiện",
        parameters=[
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("employee_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, description="int hoặc CSV '1,2,3'"),
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, description="CSV: pending,approved,rejected,canceled"),
            OpenApiParameter("is_valid", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("work_mode", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, description="CSV: onsite,remote"),
            OpenApiParameter("source", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, description="CSV: web,mobile,lark,googleforms"),
            OpenApiParameter("template_code", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, description="CSV"),
            OpenApiParameter("template_name", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("approved_by", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("requested_by", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("shift_date_from", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("shift_date_to", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("ts_in_from", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("ts_in_to", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("ts_out_from", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("ts_out_to", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("bonus_min", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("bonus_max", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: AttendanceSummaryV2ReadSerializer(many=True), 400: OpenApiResponse(), 403: OpenApiResponse()},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        _ = SearchFiltersSerializer(data=request.query_params)
        _.is_valid(raise_exception=False)
        filters = _build_search_filters(request)

        manager_id = request.query_params.get("manager_id")
        is_mgr = False
        if manager_id is not None:
            try:
                is_mgr = is_employee_manager(int(manager_id))
            except Exception:
                is_mgr = False

        if not is_mgr:
            if not filters.get("employee_id"):
                return Response({"detail": "employee_id is required for non-manager search."}, status=400)

        qs = filter_summaries(filters, order_by=["-shift_instance__date", "employee_id"])
        return Response(AttendanceSummaryV2ReadSerializer(qs, many=True).data)
    
    @extend_schema(
        tags=["Attendance V2"],
        summary="Đăng ký ca tuần tới (đơn giản)",
        description="Nhận danh sách shift_instance_id cho 7 ngày tiếp theo. Trả về created/updated/skipped/errors.",
        request=BulkRegisterSerializer,
        responses={
            200: OpenApiTypes.OBJECT,  # đơn giản: object chung
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Request mẫu",
                value={"employee_id": 204, "shift_instance_ids": [11, 12, 18], "requested_by": 204},
                request_only=True,
            ),
            OpenApiExample(
                "Response mẫu",
                value={
                    "week_start": "2025-10-13",
                    "week_end": "2025-10-19",
                    "total_input": 3,
                    "created": [301, 302],
                    "updated": [],
                    "skipped": [{"shift_instance_id": 18, "reason": "Not in next-week window"}],
                    "errors": []
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="bulk-register-week")
    def bulk_register_week(self, request):
        ser = BulkRegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        result = register_shifts_bulk_for_next_week(
            employee_id=data["employee_id"],
            shift_instance_ids=data["shift_instance_ids"],
            requested_by=data.get("requested_by"),
            actor_is_manager=False,  # hoặc is_employee_manager(data["employee_id"])
        )
        return Response(result, status=200)
