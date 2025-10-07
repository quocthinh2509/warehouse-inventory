# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List

from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample,
    OpenApiResponse
)
from drf_spectacular.types import OpenApiTypes

from erp_the20.models import LeaveRequest
from erp_the20.serializers.leave_serializer import (
    LeaveRequestReadSerializer,
    LeaveCreateSerializer,
    LeaveUpdateSerializer,
    LeaveCancelSerializer,
    LeaveManagerDecisionSerializer,
)
from erp_the20.services.leave_service import (
    create_leave as svc_create_leave,
    update_leave as svc_update_leave,
    delete_leave as svc_delete_leave,
    cancel_leave as svc_cancel_leave,
    manager_decide as svc_manager_decide,
)
from erp_the20.selectors.leave_selector import (
    list_my_leaves,
    list_pending_for_manager,
    filter_leaves,
)
from erp_the20.selectors.user_selector import (
    is_employee_manager,
    get_external_users_map,
)

def _build_user_map_for_qs(qs) -> dict:
    ids = list(qs.values_list("employee_id", flat=True).distinct())
    return get_external_users_map(ids)

@extend_schema_view(
    create=extend_schema(
        tags=["Leave"],
        summary="Tạo đơn nghỉ",
        description="Nhân viên tạo đơn nghỉ. Truyền kèm manager_id để gửi email thông báo cho quản lý.",
        request=LeaveCreateSerializer,
        responses={
            201: LeaveRequestReadSerializer,
            400: OpenApiResponse(description="Bad Request"),
        },
        examples=[
            OpenApiExample(
                "Tạo đơn nghỉ theo ngày",
                value={
                    "employee_id": 204,
                    "manager_id": 13,              # <-- thêm trường bắt buộc
                    "start_date": "2025-10-09",
                    "end_date": "2025-10-10",
                    "hours": None,
                    "paid": False,
                    "reason": "Nghỉ phép cá nhân"
                },
                request_only=True,
            )
        ],
    ),
    update=extend_schema(
        tags=["Leave"],
        summary="Cập nhật đơn nghỉ",
        description="Nhân viên sửa đơn ở trạng thái submitted.",
        request=LeaveUpdateSerializer,
        responses={200: LeaveRequestReadSerializer, 400: OpenApiResponse()},
    ),
    destroy=extend_schema(
        tags=["Leave"],
        summary="Xoá đơn nghỉ",
        description="Xoá cứng đơn nghỉ (submitted). Truyền employee_id qua query/body.",
        parameters=[OpenApiParameter("employee_id", OpenApiTypes.INT, OpenApiParameter.QUERY, description="ID nhân viên (owner)")],
        responses={204: OpenApiResponse(description="Deleted")},
    ),
)
class LeaveRequestViewSet(
    viewsets.GenericViewSet,
    mixins.DestroyModelMixin,
):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestReadSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request):
        ser = LeaveCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        # (Không bắt buộc xác thực quyền Manager ở đây — chỉ dùng để gửi mail)
        try:
            obj = svc_create_leave(**ser.validated_data)  # validated_data đã có manager_id
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        umap = get_external_users_map([obj.employee_id])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data, status=201)

    def update(self, request, pk=None):
        payload = dict(request.data)
        payload["id"] = pk
        ser = LeaveUpdateSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        try:
            obj = svc_update_leave(
                leave_id=int(pk),
                **{k: v for k, v in ser.validated_data.items() if k not in ("id",)}
            )
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        umap = get_external_users_map([obj.employee_id])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data)

    def destroy(self, request, pk=None):
        employee_id = request.query_params.get("employee_id") or request.data.get("employee_id")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response({"detail": "Missing/invalid employee_id"}, status=400)
        try:
            svc_delete_leave(leave_id=int(pk), employee_id=employee_id)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(status=204)

    @extend_schema(
        tags=["Leave"],
        summary="Huỷ đơn (nhân viên)",
        description="Nhân viên huỷ đơn của mình: chuyển trạng thái `cancelled`.",
        request=LeaveCancelSerializer,
        responses={200: LeaveRequestReadSerializer, 400: OpenApiResponse()},
    )
    @action(detail=True, methods=["put"], url_path="cancel")
    def cancel(self, request, pk=None):
        ser = LeaveCancelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            obj = svc_cancel_leave(leave_id=int(pk), actor_employee_id=ser.validated_data["employee_id"], as_manager=False)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        umap = get_external_users_map([obj.employee_id])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data)

    @extend_schema(
        tags=["Leave"],
        summary="Quản lý phê duyệt / từ chối",
        description="Manager quyết định đơn: `approve=true` → `approved`, `false` → `rejected`. Ghi nhận `decided_by`, `decision_ts` và gửi mail cho nhân viên.",
        request=LeaveManagerDecisionSerializer,
        responses={200: LeaveRequestReadSerializer, 400: OpenApiResponse()},
    )
    @action(detail=True, methods=["put"], url_path="decide")
    def decide(self, request, pk=None):
        ser = LeaveManagerDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        manager_id = ser.validated_data["manager_id"]
        approve = ser.validated_data["approve"]
        if not is_employee_manager(manager_id):
            return Response({"detail": "Manager privilege required."}, status=403)

        try:
            obj = svc_manager_decide(leave_id=int(pk), manager_id=manager_id, approve=approve)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        umap = get_external_users_map([obj.employee_id])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data)

    @extend_schema(
        tags=["Leave"],
        summary="Danh sách đơn của tôi",
        parameters=[OpenApiParameter("employee_id", OpenApiTypes.INT, OpenApiParameter.QUERY, description="ID nhân viên")],
        responses={200: LeaveRequestReadSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="my")
    def my_leaves(self, request):
        employee_id = request.query_params.get("employee_id")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response({"detail": "Missing/invalid employee_id"}, status=400)
        qs = list_my_leaves(employee_id)
        umap = _build_user_map_for_qs(qs)
        return Response(LeaveRequestReadSerializer(qs, many=True, context={"user_map": umap}).data)

    @extend_schema(
        tags=["Leave"],
        summary="Danh sách đơn pending (manager)",
        parameters=[
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY, description="Manager ID (xác thực quyền)"),
            OpenApiParameter("from", OpenApiTypes.DATE, OpenApiParameter.QUERY, description="Từ ngày (YYYY-MM-DD)"),
            OpenApiParameter("to", OpenApiTypes.DATE, OpenApiParameter.QUERY, description="Đến ngày (YYYY-MM-DD)"),
        ],
        responses={200: LeaveRequestReadSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="pending")
    def pending(self, request):
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
        umap = _build_user_map_for_qs(qs)
        return Response(LeaveRequestReadSerializer(qs, many=True, context={"user_map": umap}).data)

    @extend_schema(
        tags=["Leave"],
        summary="Tìm kiếm đơn nghỉ (lọc nhiều điều kiện)",
        parameters=[
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY, description="Manager ID (nếu là quản lý)"),
            OpenApiParameter("employee_id", OpenApiTypes.STR, OpenApiParameter.QUERY, description="1 hoặc nhiều ID: '204' hoặc '204,205'"),
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, description="submitted|approved|rejected|cancelled"),
            OpenApiParameter("from", OpenApiTypes.DATE, OpenApiParameter.QUERY, description="start_date ≥ from"),
            OpenApiParameter("to", OpenApiTypes.DATE, OpenApiParameter.QUERY, description="end_date ≤ to"),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Tìm theo lý do"),
        ],
        responses={200: LeaveRequestReadSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        filters = request.query_params
        manager_id = request.query_params.get("manager_id")
        is_mgr = False
        if manager_id is not None:
            try:
                is_mgr = is_employee_manager(int(manager_id))
            except Exception:
                is_mgr = False
        if not is_mgr and not filters.get("employee_id"):
            return Response({"detail": "employee_id is required for non-manager search."}, status=400)

        qs = filter_leaves(filters, order_by=["-start_date", "-created_at"])
        umap = _build_user_map_for_qs(qs)
        return Response(LeaveRequestReadSerializer(qs, many=True, context={"user_map": umap}).data)
