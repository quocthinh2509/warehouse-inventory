# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict
from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from erp_the20.utils.pagination import DefaultPagination
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
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
    # get_all_manager,
)

# optional auth helpers
try:
    from erp_the20.selectors.user_selector import is_employee_manager, get_external_users_map
except Exception:
    def is_employee_manager(_): return False
    def get_external_users_map(_): return {}

# ---- OpenAPI common params for pagination
PAGE_PARAMS = [
    OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False, description="Trang (mặc định 1)"),
    OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False, description="Kích thước trang (mặc định 20, tối đa 200)"),
]

def _build_user_map_for_qs(qs) -> dict:
    ids = set(qs.values_list("employee_id", flat=True).distinct())
    # include cả người nhận bàn giao nếu có
    try:
        handover_ids = qs.values_list("handover_to_employee_id", flat=True).distinct()
        for x in handover_ids:
            if x:
                ids.add(x)
    except Exception:
        pass
    return get_external_users_map(list(ids))


@extend_schema_view(
    retrieve=extend_schema(
        tags=["Leave"],
        summary="Lấy chi tiết đơn nghỉ theo ID",
        parameters=[OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH, description="Leave ID")],
        responses={200: LeaveRequestReadSerializer, 404: OpenApiResponse(description="Not found")},
    ),
    create=extend_schema(
        tags=["Leave"],
        summary="Tạo đơn nghỉ (employee)",
        description="Nhân viên tạo đơn nghỉ (Status=SUBMITTED). Truyền kèm `manager_id` để thông báo.",
        request=LeaveCreateSerializer,
        responses={201: LeaveRequestReadSerializer, 400: OpenApiResponse(description="Bad Request")},
        examples=[
            OpenApiExample(
                "Annual leave (full days)",
                value={
                    "employee_id": 204,
                    "manager_id": 13,
                    "leave_type": LeaveRequest.LeaveType.ANNUAL,
                    "start_date": "2025-10-09",
                    "end_date": "2025-10-10",
                    "hours": None,
                    "paid": True,
                    "reason": "Family event",
                    # NEW: bàn giao
                    "handover_to_employee_id": 205,
                    "handover_content": "Đã bàn giao file báo cáo tuần cho bạn A",
                },
                request_only=True,
            )
        ],
    ),
    update=extend_schema(
        tags=["Leave"],
        summary="Cập nhật đơn nghỉ (employee)",
        description="Chỉ sửa được khi Status=SUBMITTED.",
        request=LeaveUpdateSerializer,
        responses={200: LeaveRequestReadSerializer, 400: OpenApiResponse()},
    ),
    destroy=extend_schema(
        tags=["Leave"],
        summary="Xoá đơn nghỉ (employee)",
        description="Xoá cứng khi Status=SUBMITTED. Truyền `employee_id` qua query/body.",
        parameters=[OpenApiParameter("employee_id", OpenApiTypes.INT, OpenApiParameter.QUERY, description="Owner employee_id")],
        responses={204: OpenApiResponse(description="Deleted")},
    ),
)
class LeaveRequestViewSet(
    viewsets.GenericViewSet,
    mixins.DestroyModelMixin,
    mixins.RetrieveModelMixin,
):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestReadSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = DefaultPagination

    def retrieve(self, request, pk=None):
        obj = self.get_object()
        umap = get_external_users_map([obj.employee_id, getattr(obj, "handover_to_employee_id", None)])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data)

    def create(self, request):
        ser = LeaveCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            obj = svc_create_leave(**ser.validated_data)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        umap = get_external_users_map([obj.employee_id, getattr(obj, "handover_to_employee_id", None)])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data, status=201)

    def update(self, request, pk=None):
        # KHÔNG đẩy 'id' thừa vào serializer để tránh lỗi "unexpected field"
        ser = LeaveUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            obj = svc_update_leave(leave_id=int(pk), **ser.validated_data)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        umap = get_external_users_map([obj.employee_id, getattr(obj, "handover_to_employee_id", None)])
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
        summary="Huỷ đơn (employee)",
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
        umap = get_external_users_map([obj.employee_id, getattr(obj, "handover_to_employee_id", None)])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data)

    @extend_schema(
        tags=["Leave"],
        summary="Quản lý phê duyệt / từ chối",
        description="`approve=true` → APPROVED, `false` → REJECTED",
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
        umap = get_external_users_map([obj.employee_id, getattr(obj, "handover_to_employee_id", None)])
        return Response(LeaveRequestReadSerializer(obj, context={"user_map": umap}).data)

    @extend_schema(
        tags=["Leave"],
        summary="Danh sách đơn của tôi",
        parameters=PAGE_PARAMS + [
            OpenApiParameter("employee_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
        ],
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
        page = self.paginate_queryset(qs)
        umap = _build_user_map_for_qs(qs)

        if page is not None:
            ser = LeaveRequestReadSerializer(page, many=True, context={"user_map": umap})
            return self.get_paginated_response(ser.data)

        ser = LeaveRequestReadSerializer(qs, many=True, context={"user_map": umap})
        return Response(ser.data)

    @extend_schema(
        tags=["Leave"],
        summary="Danh sách pending cho manager",
        parameters=PAGE_PARAMS + [
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("from", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("to", OpenApiTypes.DATE, OpenApiParameter.QUERY),
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
        page = self.paginate_queryset(qs)
        umap = _build_user_map_for_qs(qs)

        if page is not None:
            ser = LeaveRequestReadSerializer(page, many=True, context={"user_map": umap})
            return self.get_paginated_response(ser.data)

        ser = LeaveRequestReadSerializer(qs, many=True, context={"user_map": umap})
        return Response(ser.data)

    @extend_schema(
        tags=["Leave"],
        summary="Tìm kiếm đơn nghỉ (lọc nhiều điều kiện)",
        parameters=PAGE_PARAMS + [
            OpenApiParameter("manager_id", OpenApiTypes.INT, OpenApiParameter.QUERY, description="Nếu là manager, có thể không truyền employee_id"),
            OpenApiParameter("employee_id", OpenApiTypes.STR, OpenApiParameter.QUERY, description="1 hoặc nhiều ID: '204' hoặc '204,205'"),
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, description="VD: '0,1' (SUBMITTED, APPROVED)"),
            OpenApiParameter("leave_type", OpenApiTypes.STR, OpenApiParameter.QUERY, description="'0,3,4'..."),
            OpenApiParameter("start_from", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("start_to", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("end_from", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("end_to", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("handover_to", OpenApiTypes.STR, OpenApiParameter.QUERY, description="lọc theo người nhận bàn giao: '205' hoặc '205,206'"),
            OpenApiParameter("handover_to_employee_id", OpenApiTypes.STR, OpenApiParameter.QUERY, description="alias của handover_to"),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Tìm theo lý do"),
        ],
        responses={200: LeaveRequestReadSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        filters: Dict[str, Any] = request.query_params
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
        page = self.paginate_queryset(qs)
        umap = _build_user_map_for_qs(qs)

        if page is not None:
            ser = LeaveRequestReadSerializer(page, many=True, context={"user_map": umap})
            return self.get_paginated_response(ser.data)

        ser = LeaveRequestReadSerializer(qs, many=True, context={"user_map": umap})
        return Response(ser.data)

    
