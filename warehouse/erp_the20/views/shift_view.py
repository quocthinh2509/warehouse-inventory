from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiExample, OpenApiResponse,
)

from drf_spectacular.types import OpenApiTypes

from erp_the20.selectors.shift_selector import (
    list_shift_templates, get_by_id
)
from erp_the20.serializers.shift_serializer import (
    ShiftTemplateReadSerializer, ShiftTemplateWriteSerializer
)
from erp_the20.services.shift_service import (
    create_shift_template, update_shift_template_versioned,
    soft_delete_shift_template, 
    #restore_shift_template
)




@extend_schema_view(
    list=extend_schema(
        tags=["ShiftTemplate"],
        summary="Danh sách Shift Templates",
        description="Liệt kê các shift template (mặc định chỉ bản active).",
        parameters=[
            OpenApiParameter(name="q", description="Tìm theo code/name (contains)", required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name="overnight", description="Lọc ca qua đêm (true/false)", required=False, type=OpenApiTypes.BOOL),
            OpenApiParameter(name="ordering", description='Sắp xếp, ví dụ: "code" hoặc "-created_at"', required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name="include_deleted", description="Bao gồm bản đã soft-delete (true/false)", required=False, type=OpenApiTypes.BOOL),
            OpenApiParameter(name="page", description="Trang (nếu dùng pagination)", required=False, type=OpenApiTypes.INT),
        ],
        responses={200: ShiftTemplateReadSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Ví dụ list",
                value={"count": 1, "results": [
                    {"id": 1, "code": "MORN", "name": "Morning", "start_time": "08:00:00",
                     "end_time": "17:00:00", "break_minutes": 60, "overnight": False,
                     "pay_factor": "1.00", "created_at": "2025-10-08T01:02:03Z",
                     "updated_at": "2025-10-08T01:02:03Z", "deleted_at": None}
                ]}
            )
        ],
    ),
    retrieve=extend_schema(
        tags=["ShiftTemplate"],
        summary="Xem chi tiết",
        responses={200: ShiftTemplateReadSerializer},
    ),
    create=extend_schema(
        tags=["ShiftTemplate"],
        summary="Tạo mới",
        request=ShiftTemplateWriteSerializer,
        responses={201: ShiftTemplateReadSerializer, 400: OpenApiResponse(description="Bad Request")},
        examples=[
            OpenApiExample(
                "Payload",
                value={"code": "MORN", "name": "Morning", "start_time": "08:00:00",
                       "end_time": "17:00:00", "break_minutes": 60, "overnight": False, "pay_factor": "1.00"}
            )
        ],
    ),
    update=extend_schema(
        tags=["ShiftTemplate"],
        summary="Cập nhật (versioning: archive bản cũ + tạo bản mới)",
        request=ShiftTemplateWriteSerializer,
        responses={200: ShiftTemplateReadSerializer},
    ),
    partial_update=extend_schema(
        tags=["ShiftTemplate"],
        summary="Cập nhật một phần (versioning)",
        request=ShiftTemplateWriteSerializer,
        responses={200: ShiftTemplateReadSerializer},
    ),
    destroy=extend_schema(
        tags=["ShiftTemplate"],
        summary="Xóa mềm (soft-delete)",
        responses={204: OpenApiResponse(description="No Content")},
    ),
)

class ShiftTemplateViewSet(viewsets.ViewSet):
    """
    ShiftTemplate CRUD:
    - UPDATE theo versioning (archive + create)
    - DELETE là soft-delete (set deleted_at)
    """
    # permission_classes = [permissions.IsAuthenticated]  # đổi nếu chưa dùng auth

    def _get_object(self, pk: int, include_deleted: bool = False):
        obj = get_by_id(pk, include_deleted=include_deleted)
        if not obj:
            raise NotFound("ShiftTemplate không tồn tại.")
        return obj

    # GET /shift-templates/?q=&overnight=&ordering=&include_deleted=
    def list(self, request):
        q = request.query_params.get("q")
        ordering = request.query_params.get("ordering")  # vd: "code" hoặc "-created_at"
        overnight = request.query_params.get("overnight")
        include_deleted = request.query_params.get("include_deleted") in ("1", "true", "True")
        if overnight is not None:
            overnight = overnight in ("1", "true", "True")

        qs = list_shift_templates(q=q, overnight=overnight, ordering=ordering, include_deleted=include_deleted)
        page = self.paginate_queryset(qs)
        data = ShiftTemplateReadSerializer(page or qs, many=True).data
        return self.get_paginated_response(data) if page is not None else Response(data)

    # GET /shift-templates/{id}/
    def retrieve(self, request, pk=None):
        instance = self._get_object(pk, include_deleted=True)
        return Response(ShiftTemplateReadSerializer(instance).data)

    # POST /shift-templates/
    def create(self, request):
        ser = ShiftTemplateWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        instance = create_shift_template(ser.validated_data)
        return Response(ShiftTemplateReadSerializer(instance).data, status=status.HTTP_201_CREATED)

    # PUT /shift-templates/{id}/
    def update(self, request, pk=None):
        old = self._get_object(pk, include_deleted=True)
        ser = ShiftTemplateWriteSerializer(old, data=request.data)  # validate theo rule hiện tại
        ser.is_valid(raise_exception=True)
        new_obj = update_shift_template_versioned(old, ser.validated_data)
        return Response(ShiftTemplateReadSerializer(new_obj).data, status=status.HTTP_200_OK)

    # PATCH /shift-templates/{id}/
    def partial_update(self, request, pk=None):
        old = self._get_object(pk, include_deleted=True)
        ser = ShiftTemplateWriteSerializer(old, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        new_obj = update_shift_template_versioned(old, ser.validated_data)
        return Response(ShiftTemplateReadSerializer(new_obj).data, status=status.HTTP_200_OK)

    # DELETE /shift-templates/{id}/  (soft-delete)
    def destroy(self, request, pk=None):
        instance = self._get_object(pk, include_deleted=True)
        soft_delete_shift_template(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # # POST /shift-templates/{id}/restore/
    # @action(detail=True, methods=["post"])
    # def restore(self, request, pk=None):
    #     instance = self._get_object(pk, include_deleted=True)
    #     try:
    #         restore_shift_template(instance)
    #     except ValidationError as e:
    #         return Response({"detail": e.detail if hasattr(e, "detail") else str(e)}, status=400)
    #     return Response(ShiftTemplateReadSerializer(instance).data)

    # ===== Pagination helpers (DRF PageNumberPagination) =====
    def paginate_queryset(self, queryset):
        if hasattr(self, "paginator") and self.paginator:
            return self.paginator.paginate_queryset(queryset, self.request, view=self)
        try:
            from rest_framework.pagination import PageNumberPagination
            self.paginator = PageNumberPagination()
            return self.paginator.paginate_queryset(queryset, self.request, view=self)
        except Exception:
            return None

    def get_paginated_response(self, data):
        return self.paginator.get_paginated_response(data)
