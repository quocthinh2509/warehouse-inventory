from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import datetime, date

from erp_the20.serializers.shift_serializer import (
    ShiftTemplateWriteSerializer, ShiftTemplateReadSerializer,
    ShiftInstanceWriteSerializer, ShiftInstanceReadSerializer,
    ShiftInstanceQuerySerializer,
)
from erp_the20.services.shift_service import (
    create_shift_template, update_shift_template, delete_shift_template,
    create_shift_instance, update_shift_instance, delete_shift_instance,

)
from erp_the20.selectors.shift_selector import (
    list_shift_templates, get_shift_template,
    list_shift_instances, get_shift_instance,
    instances_around,list_today_shift_instances,
)

# ============== SHIFT TEMPLATE ==============

class ShiftTemplateListCreate(APIView):
    @extend_schema(
        responses=ShiftTemplateReadSerializer(many=True),
        description="Danh sách ca làm (template)."
    )
    def get(self, request):
        qs = list_shift_templates()
        return Response(ShiftTemplateReadSerializer(qs, many=True).data)

    @extend_schema(
        request=ShiftTemplateWriteSerializer,
        responses=ShiftTemplateReadSerializer,
        description="Tạo mới ca làm (template)."
    )
    def post(self, request):
        ser = ShiftTemplateWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = create_shift_template(ser.validated_data)
        return Response(ShiftTemplateReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class ShiftTemplateDetail(APIView):
    @extend_schema(
        request=ShiftTemplateWriteSerializer,
        responses=ShiftTemplateReadSerializer,
        description="Cập nhật ca làm (template) theo ID."
    )
    def put(self, request, pk):
        template = get_shift_template(pk)
        if not template:
            return Response({"detail": "Not found"}, status=404)
        ser = ShiftTemplateWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updated = update_shift_template(template, ser.validated_data)
        return Response(ShiftTemplateReadSerializer(updated).data)

    @extend_schema(description="Xóa ca làm (template) theo ID.")
    def delete(self, request, pk):
        template = get_shift_template(pk)
        if not template:
            return Response({"detail": "Not found"}, status=404)
        delete_shift_template(template)
        return Response(status=204)


# ============== SHIFT INSTANCE ==============

class ShiftInstanceListCreate(APIView):
    @extend_schema(
        parameters=[OpenApiParameter("date_from", str, description="YYYY-MM-DD"),
                    OpenApiParameter("date_to", str, description="YYYY-MM-DD"),
                    OpenApiParameter("status", str)],
        responses=ShiftInstanceReadSerializer(many=True),
        description="Danh sách ca làm cụ thể (instance) với filter ngày."
    )
    def get(self, request):
        qser = ShiftInstanceQuerySerializer(data=request.query_params)
        qser.is_valid(raise_exception=True)
        df = qser.validated_data.get("date_from")
        dt = qser.validated_data.get("date_to")
        status_q = request.query_params.get("status")
        qs = list_shift_instances(df, dt, status_q)
        return Response(ShiftInstanceReadSerializer(qs, many=True).data)

    @extend_schema(
        request=ShiftInstanceWriteSerializer,
        responses=ShiftInstanceReadSerializer,
        description="Tạo mới ca làm cụ thể (instance)."
    )
    def post(self, request):
        ser = ShiftInstanceWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = create_shift_instance(ser.validated_data)
        return Response(ShiftInstanceReadSerializer(obj).data, status=201)


class ShiftInstanceDetail(APIView):
    @extend_schema(
        request=ShiftInstanceWriteSerializer,
        responses=ShiftInstanceReadSerializer,
        description="Cập nhật ca làm cụ thể theo ID."
    )
    def put(self, request, pk):
        instance = get_shift_instance(pk)
        if not instance:
            return Response({"detail": "Not found"}, status=404)
        ser = ShiftInstanceWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updated = update_shift_instance(instance, ser.validated_data)
        return Response(ShiftInstanceReadSerializer(updated).data)

    @extend_schema(description="Xóa ca làm cụ thể theo ID.")
    def delete(self, request, pk):
        instance = get_shift_instance(pk)
        if not instance:
            return Response({"detail": "Not found"}, status=404)
        delete_shift_instance(instance)
        return Response(status=204)


class ShiftInstancesTodayView(APIView):
    @extend_schema(
        responses=ShiftInstanceReadSerializer(many=True),
        description="Danh sách ca làm cụ thể (instance) trong ngày hôm nay."
    )
    def get(self, request):
        qs = list_today_shift_instances()
        return Response(ShiftInstanceReadSerializer(qs, many=True).data)