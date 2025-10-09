# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from erp_the20.models import Attendance
from erp_the20.selectors.attendance_selector import (
    filter_attendances,
    list_my_pending,
    list_pending_for_manager,
)
from erp_the20.selectors.user_selector import (
    is_employee_manager,
    get_external_users_map,
)
from erp_the20.serializers.attendance_serializer import (
    ApproveDecisionSerializer,
    AttendanceCreateSerializer,
    AttendanceReadSerializer,
    AttendanceUpdateSerializer,
    BatchDecisionSerializer,
    BatchRegisterSerializer,
    CancelSerializer,
    ManagerCancelSerializer,
    SearchFiltersSerializer,
)
from erp_the20.services.attendance_service import (
    approve_attendance,
    batch_decide_attendance,
    batch_register_attendance,
    cancel_by_employee,
    create_attendance,
    manager_cancel_attendance,
    reject_attendance,
    restore_attendance,
    soft_delete_attendance,
    update_attendance,
)


# -----------------------
# Helpers
# -----------------------
def _qp_get_multi(request, key: str) -> List[str]:
    vs = request.query_params.getlist(key)
    if not vs:
        raw = request.query_params.get(key)
        if raw:
            vs = [x for x in raw.split(",") if x != ""]
    out: List[str] = []
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
        "shift_date_from": request.query_params.get("shift_date_from") or request.query_params.get("from"),
        "shift_date_to": request.query_params.get("shift_date_to") or request.query_params.get("to"),
        "date_from": request.query_params.get("date_from"),
        "date_to": request.query_params.get("date_to"),
        "ts_in_from": request.query_params.get("ts_in_from"),
        "ts_in_to": request.query_params.get("ts_in_to"),
        "ts_out_from": request.query_params.get("ts_out_from"),
        "ts_out_to": request.query_params.get("ts_out_to"),
        "bonus_min": request.query_params.get("bonus_min"),
        "bonus_max": request.query_params.get("bonus_max"),
        "q": request.query_params.get("q"),
    }


def _iter_objs(objs) -> Iterable[Attendance]:
    if objs is None:
        return []
    if isinstance(objs, QuerySet):
        return list(objs)
    if isinstance(objs, (list, tuple, set)):
        return objs
    return [objs]


def _build_users_map_from_objs(objs) -> dict:
    ids = set()
    for o in _iter_objs(objs):
        for uid in (o.employee_id, o.requested_by, o.approved_by):
            if uid:
                ids.add(int(uid))
    return get_external_users_map(list(ids)) if ids else {}


# -----------------------
# ViewSet
# -----------------------
@extend_schema_view(
    list=extend_schema(
        tags=["Attendance"],
        summary="Tìm kiếm / liệt kê Attendance",
        parameters=[OpenApiParameter("include_deleted", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False)],
        responses={200: AttendanceReadSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Attendance"],
        summary="Chi tiết Attendance",
        parameters=[OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH)],
        responses={200: AttendanceReadSerializer, 404: OpenApiResponse()},
    ),
    create=extend_schema(
        tags=["Attendance"],
        summary="Tạo Attendance (đăng ký ca/ngày)",
        request=AttendanceCreateSerializer,
        responses={201: AttendanceReadSerializer, 400: OpenApiResponse()},
        examples=[
            OpenApiExample(
                "Create",
                value={"employee_id": 204, "shift_template": 3, "date": "2025-10-15", "source": 0, "work_mode": 0},
                request_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        tags=["Attendance"],
        summary="Cập nhật Attendance",
        request=AttendanceUpdateSerializer,
        responses={200: AttendanceReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
    ),
    destroy=extend_schema(
        tags=["Attendance"],
        summary="Xoá mềm Attendance",
        responses={204: OpenApiResponse(description="Soft-deleted")},
    ),
)
class AttendanceViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    """
    Attendance CRUD + hành động bổ sung:
    - restore, cancel (employee), approve/reject/manager-cancel (manager)
    - my-pending, pending (manager), search
    - batch-register (ALL-OR-NOTHING), batch-decide
    """
    queryset = Attendance.objects.all()
    serializer_class = AttendanceReadSerializer
    permission_classes = [permissions.AllowAny]

    # GET /attendance/
    def list(self, request):
        _ = SearchFiltersSerializer(data=request.query_params)
        _.is_valid(raise_exception=False)

        filters = _build_search_filters(request)
        include_deleted = str(request.query_params.get("include_deleted", "")).lower() in ("1", "true", "t", "yes", "y")
        qs = filter_attendances(filters, include_deleted=include_deleted, order_by=["-date", "employee_id"])

        page = self.paginate_queryset(qs)
        if page is not None:
            users_map = _build_users_map_from_objs(page)
            ser = AttendanceReadSerializer(page, many=True, context={"users_map": users_map})
            return self.get_paginated_response(ser.data)

        users_map = _build_users_map_from_objs(qs)
        ser = AttendanceReadSerializer(qs, many=True, context={"users_map": users_map})
        return Response(ser.data)

    # GET /attendance/{id}/
    def retrieve(self, request, pk=None):
        obj = get_object_or_404(Attendance, id=pk)
        users_map = _build_users_map_from_objs(obj)
        return Response(AttendanceReadSerializer(obj, context={"users_map": users_map}).data)

    # POST /attendance/
    def create(self, request):
        ser = AttendanceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            obj = create_attendance(
                employee_id=data["employee_id"],
                shift_template_id=data["shift_template"],
                date=data["date"],
                ts_in=data.get("ts_in"),
                ts_out=data.get("ts_out"),
                source=data["source"],
                work_mode=data["work_mode"],
                bonus=data.get("bonus"),
                requested_by=data.get("employee_id"),
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        users_map = _build_users_map_from_objs(obj)
        return Response(AttendanceReadSerializer(obj, context={"users_map": users_map}).data, status=status.HTTP_201_CREATED)
        

    # PATCH /attendance/{id}/
    def partial_update(self, request, pk=None):
        payload = dict(request.data)
        payload["employee_id"] = payload.get("employee_id") or request.data.get("employee_id")

        ser = AttendanceUpdateSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        actor_is_mgr = is_employee_manager(data["employee_id"])
        try:
            obj = update_attendance(
                target_id=int(pk),
                actor_employee_id=data["employee_id"],
                shift_template_id=data.get("shift_template"),
                date=data.get("date"),
                ts_in=data.get("ts_in"),
                ts_out=data.get("ts_out"),
                source=data.get("source"),
                work_mode=data.get("work_mode"),
                bonus=data.get("bonus"),
                requested_by=data.get("requested_by"),
                actor_is_manager=actor_is_mgr,
            )
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        users_map = _build_users_map_from_objs(obj)
        return Response(AttendanceReadSerializer(obj, context={"users_map": users_map}).data)

    # DELETE /attendance/{id}/ (soft)
    def destroy(self, request, pk=None):
        try:
            soft_delete_attendance(target_id=int(pk))
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # POST /attendance/{id}/restore/
    @extend_schema(tags=["Attendance"], summary="Khôi phục bản ghi đã xoá mềm", responses={200: AttendanceReadSerializer, 400: OpenApiResponse()})
    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        try:
            obj = restore_attendance(target_id=int(pk))
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        users_map = _build_users_map_from_objs(obj)
        return Response(AttendanceReadSerializer(obj, context={"users_map": users_map}).data)

    # PUT /attendance/{id}/cancel/
    @extend_schema(
        tags=["Attendance"],
        summary="Nhân viên huỷ Attendance",
        request=CancelSerializer,
        responses={200: AttendanceReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
    )
    @action(detail=True, methods=["put"], url_path="cancel")
    def cancel(self, request, pk=None):
        ser = CancelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            obj = cancel_by_employee(
                actor_user_id=data["employee_id"],
                target_id=int(pk),
                actor_is_manager=is_employee_manager(data["employee_id"]),
            )
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        users_map = _build_users_map_from_objs(obj)
        return Response(AttendanceReadSerializer(obj, context={"users_map": users_map}).data)

    # PUT /attendance/{id}/approve/
    @extend_schema(
        tags=["Attendance"],
        summary="Quản lý duyệt / từ chối",
        request=ApproveDecisionSerializer,
        responses={200: AttendanceReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
        examples=[
            OpenApiExample("Approve", value={"manager_id": 1, "approve": True, "override_overlap": False}, request_only=True),
            OpenApiExample("Reject", value={"manager_id": 1, "approve": False, "reason": "Lý do từ chối"}, request_only=True),
        ],
    )
    @action(detail=True, methods=["put"], url_path="approve")
    def approve_or_reject(self, request, pk=None):
        ser = ApproveDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        manager_id = data.get("manager_id")
        if manager_id is None:
            return Response({"detail": "manager_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not is_employee_manager(manager_id):
            return Response({"detail": "Manager privilege required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            if data["approve"]:
                obj = approve_attendance(
                    manager_user_id=manager_id,
                    target_id=int(pk),
                    override_overlap=bool(data.get("override_overlap", False)),
                )
            else:
                obj = reject_attendance(manager_user_id=manager_id, target_id=int(pk), reason=data.get("reason") or "")
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        users_map = _build_users_map_from_objs(obj)
        return Response(AttendanceReadSerializer(obj, context={"users_map": users_map}).data)

    # PUT /attendance/{id}/manager-cancel/
    @extend_schema(
        tags=["Attendance"],
        summary="Quản lý huỷ Attendance",
        request=ManagerCancelSerializer,
        responses={200: AttendanceReadSerializer, 400: OpenApiResponse(), 403: OpenApiResponse()},
    )
    @action(detail=True, methods=["put"], url_path="manager-cancel")
    def manager_cancel(self, request, pk=None):
        ser = ManagerCancelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if not is_employee_manager(data["manager_id"]):
            return Response({"detail": "Manager privilege required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            obj = manager_cancel_attendance(
                manager_user_id=data["manager_id"], target_id=int(pk), reason=data.get("reason") or ""
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        users_map = _build_users_map_from_objs(obj)
        return Response(AttendanceReadSerializer(obj, context={"users_map": users_map}).data)

    # GET /attendance/my-pending?employee_id=...
    @extend_schema(
        tags=["Attendance"],
        summary="Danh sách pending của tôi",
        parameters=[OpenApiParameter("employee_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=True)],
        responses={200: AttendanceReadSerializer(many=True), 400: OpenApiResponse()},
    )
    @action(detail=False, methods=["get"], url_path="my-pending")
    def my_pending(self, request):
        employee_id = request.query_params.get("employee_id")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response({"detail": "Missing/invalid employee_id."}, status=status.HTTP_400_BAD_REQUEST)

        qs = list_my_pending(employee_id)
        users_map = _build_users_map_from_objs(qs)
        return Response(AttendanceReadSerializer(qs, many=True, context={"users_map": users_map}).data)

    # GET /attendance/pending?manager_id=...&from=YYYY-MM-DD&to=YYYY-MM-DD
    @extend_schema(
        tags=["Attendance"],
        summary="Quản lý xem danh sách pending",
        parameters=[
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("from", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("to", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: AttendanceReadSerializer(many=True), 400: OpenApiResponse(), 403: OpenApiResponse()},
    )
    @action(detail=False, methods=["get"], url_path="pending")
    def manager_pending(self, request):
        manager_id = request.query_params.get("manager_id")
        try:
            manager_id = int(manager_id)
        except (TypeError, ValueError):
            return Response({"detail": "manager_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not is_employee_manager(manager_id):
            return Response({"detail": "Manager privilege required."}, status=status.HTTP_403_FORBIDDEN)

        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        qs = list_pending_for_manager(date_from, date_to)

        users_map = _build_users_map_from_objs(qs)
        return Response(AttendanceReadSerializer(qs, many=True, context={"users_map": users_map}).data)

    # GET /attendance/search?...
    @extend_schema(
        tags=["Attendance"],
        summary="Tìm kiếm đa điều kiện",
        parameters=[
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("include_deleted", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("employee_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("is_valid", OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("work_mode", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("source", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("template_code", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("template_name", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("approved_by", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("requested_by", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("date_from", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("date_to", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: AttendanceReadSerializer(many=True), 400: OpenApiResponse(), 403: OpenApiResponse()},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        _ = SearchFiltersSerializer(data=request.query_params)
        _.is_valid(raise_exception=False)
        filters = _build_search_filters(request)

        include_deleted = str(request.query_params.get("include_deleted", "")).lower() in ("1", "true", "t", "yes", "y")
        qs = filter_attendances(filters, include_deleted=include_deleted, order_by=["-date", "employee_id"])

        page = self.paginate_queryset(qs)
        if page is not None:
            users_map = _build_users_map_from_objs(page)
            ser = AttendanceReadSerializer(page, many=True, context={"users_map": users_map})
            return self.get_paginated_response(ser.data)

        users_map = _build_users_map_from_objs(qs)
        ser = AttendanceReadSerializer(qs, many=True, context={"users_map": users_map})
        return Response(ser.data)

    # POST /attendance/batch-register/
    @extend_schema(
        tags=["Attendance"],
        summary="Đăng ký hàng loạt (ALL-OR-NOTHING)",
        description=(
            "Nhận danh sách (date, shift_template[, ts_in, ts_out]) và tạo nhiều Attendance PENDING. "
            "All-or-nothing: nếu có bất kỳ lỗi (trùng giờ nội bộ payload hoặc trùng với DB), hệ thống sẽ trả 400 "
            "và KHÔNG tạo bản ghi nào."
        ),
        request=BatchRegisterSerializer,
        responses={
            201: OpenApiResponse(description="All created"),
            400: OpenApiResponse(description="Validation error(s), none created")
        },
        examples=[
            OpenApiExample(
                "Batch register next week",
                value={
                    "employee_id": 204,
                    "default_source": 0,
                    "default_work_mode": 0,
                    "default_bonus": "0.00",
                    "items": [
                        {"date": "2025-10-13", "shift_template": 3},
                        {"date": "2025-10-14", "shift_template": 3},
                        {"date": "2025-10-15", "shift_template": 5, "ts_in": "2025-10-15T08:00:00Z", "ts_out": "2025-10-15T17:00:00Z"},
                    ],
                },
                request_only=True,
            )
        ],
    )
    @action(detail=False, methods=["post"], url_path="batch-register")
    def batch_register(self, request):
        ser = BatchRegisterSerializer(data=request.body if hasattr(request, "body") else request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        created, errors = batch_register_attendance(
            employee_id=data["employee_id"],
            items=data["items"],
            default_source=data["default_source"],
            default_work_mode=data["default_work_mode"],
            default_bonus=data.get("default_bonus") or "0.00",
        )
        payload = {
            "created": AttendanceReadSerializer(
                created,
                many=True,
                context={"users_map": _build_users_map_from_objs(created)},
            ).data,
            "errors": errors,
        }
        return Response(payload, status=status.HTTP_201_CREATED if not errors else status.HTTP_400_BAD_REQUEST)

    # PUT /attendance/batch-decide/
    @extend_schema(
        tags=["Attendance"],
        summary="Manager duyệt/từ chối hàng loạt",
        description="Mỗi item gồm id, approve(bool), reason?(reject), override_overlap?(approve). Partial success.",
        request=BatchDecisionSerializer,
        responses={200: OpenApiResponse(description="Multi-Status (partial)"), 403: OpenApiResponse(), 400: OpenApiResponse()},
        examples=[
            OpenApiExample(
                "Batch approve/reject",
                value={
                    "manager_id": 1,
                    "items": [
                        {"id": 101, "approve": True, "override_overlap": False},
                        {"id": 102, "approve": False, "reason": "Sai ca"},
                        {"id": 103, "approve": True, "override_overlap": True},
                    ],
                },
                request_only=True,
            )
        ],
    )
    @action(detail=False, methods=["put"], url_path="batch-decide")
    def batch_decide(self, request):
        ser = BatchDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        manager_id = data["manager_id"]
        if not is_employee_manager(manager_id):
            return Response({"detail": "Manager privilege required."}, status=status.HTTP_403_FORBIDDEN)

        updated, errors = batch_decide_attendance(manager_user_id=manager_id, items=data["items"])
        payload = {
            "updated": AttendanceReadSerializer(
                updated,
                many=True,
                context={"users_map": _build_users_map_from_objs(updated)},
            ).data,
            "errors": errors,
        }
        return Response(payload, status=status.HTTP_200_OK)
