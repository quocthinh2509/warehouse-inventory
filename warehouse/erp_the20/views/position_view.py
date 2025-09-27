# views/position_views.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from erp_the20.serializers.position_serializer import PositionWriteSerializer, PositionReadSerializer
from erp_the20.services.position_service import create_position, update_position, delete_position
from erp_the20.selectors.position_selector import list_all_positions, get_position_by_id

from .utils import extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors

# -----------------------------
# /api/positions/  (list + create)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Position"],
        summary="List all positions",
        responses=OpenApiResponse(PositionReadSerializer(many=True))
    ),
    post=extend_schema(
        tags=["Position"],
        summary="Create a new position",
        request=PositionWriteSerializer,
        responses={201: OpenApiResponse(PositionReadSerializer), **std_errors()}
    )
)
class PositionListCreateView(APIView):
    def get(self, request):
        """
        Lấy danh sách tất cả Position, kèm department.
        """
        positions = list_all_positions()
        data = PositionReadSerializer(positions, many=True).data
        return Response(data)

    def post(self, request):
        """
        Tạo mới Position.
        Kiểm tra code trùng trước khi tạo.
        """
        ser = PositionWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pos = create_position(ser.validated_data)
        return Response(PositionReadSerializer(pos).data, status=status.HTTP_201_CREATED)


# -----------------------------
# /api/positions/<pk>/  (get + update + delete)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Position"],
        summary="Get position details",
        parameters=[path_int("pk", "Position ID")],
        responses={200: OpenApiResponse(PositionReadSerializer), **std_errors()},
    ),
    put=extend_schema(
        tags=["Position"],
        summary="Update position (partial allowed)",
        parameters=[path_int("pk", "Position ID")],
        request=PositionWriteSerializer,
        responses={200: OpenApiResponse(PositionReadSerializer), **std_errors()},
    ),
    delete=extend_schema(
        tags=["Position"],
        summary="Delete position",
        parameters=[path_int("pk", "Position ID")],
        responses={204: OpenApiResponse(None, description="Deleted"), **std_errors()},
    ),
)
class PositionDetailView(APIView):
    def get(self, request, pk: int):
        pos = get_position_by_id(pk)
        if not pos:
            return Response({"detail": "Position not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PositionReadSerializer(pos).data)

    def put(self, request, pk: int):
        pos = get_position_by_id(pk)
        if not pos:
            return Response({"detail": "Position not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = PositionWriteSerializer(instance=pos, data=request.data, partial=True)  # partial=True cho phép cập nhật một phần
        ser.is_valid(raise_exception=True)
        updated = update_position(pos, ser.validated_data)
        return Response(PositionReadSerializer(updated).data)

    def delete(self, request, pk: int):
        pos = get_position_by_id(pk)
        if not pos:
            return Response({"detail": "Position not found"}, status=status.HTTP_404_NOT_FOUND)
        delete_position(pos)
        return Response(status=status.HTTP_204_NO_CONTENT)
