from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from erp_the20.serializers.position_serializer import PositionReadSerializer, PositionWriteSerializer
from erp_the20.services.position_service import create_position, update_position, delete_position
from erp_the20.selectors.position_selector import list_all_positions, get_position_by_id
from .utils import extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors




@extend_schema_view(
    get=extend_schema(tags=["Position"], summary="List all positions, lấy tất cả vị trí",
                      responses=OpenApiResponse(PositionReadSerializer(many=True))),
    post=extend_schema(tags=["Position"], summary="Create position, tạo vị trí",
                       request=PositionWriteSerializer,
                       responses={201: OpenApiResponse(PositionReadSerializer), **std_errors()}),
)
class PositionListCreateView(APIView):
    """
    GET: trả danh sách tất cả vị trí
    POST: tạo vị trí (qua service)
    """

    def get(self, request):
        positions = list_all_positions()
        data = PositionReadSerializer(positions, many=True).data
        return Response(data)

    def post(self, request):
        ser = PositionWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pos = create_position(ser.validated_data)
        return Response(PositionReadSerializer(pos).data, status=status.HTTP_201_CREATED)

# -----------------------------
# /api/positions/<pk>/  (put + delete)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Position"], summary="Get position by ID, lấy vị trí theo ID",
        parameters=[path_int("pk", "Position ID")],
        responses={200: OpenApiResponse(PositionReadSerializer), **std_errors()},
    ),
    put=extend_schema(
        tags=["Position"], summary="Update position, cập nhật vị trí",
        parameters=[path_int("pk", "Position ID")],
        request=PositionWriteSerializer,
        responses={200: OpenApiResponse(PositionReadSerializer), **std_errors()},
    ),
    delete=extend_schema(
        tags=["Position"], summary="Delete position, xóa vị trí",
        parameters=[path_int("pk", "Position ID")],
        responses={204: OpenApiResponse(description="No Content"), **std_errors()},
    ),
)
class PositionDetailView(APIView):
    """
    GET: lấy vị trí theo ID
    PUT: cập nhật vị trí (qua service)
    DELETE: xóa vị trí (qua service)
    """
    def get(self, request, pk: int):
        pos = get_position_by_id(pk)
        if not pos:
            return Response({"detail": "Position not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PositionReadSerializer(pos).data)

    def put(self, request, pk: int):
        pos = get_position_by_id(pk)
        if not pos:
            return Response({"detail": "Position not found"}, status=status.HTTP_404_NOT_FOUND)
        
        ser = PositionWriteSerializer(instance=pos, data=request.data, partial=False)
        ser.is_valid(raise_exception=True)
        pos = update_position(pos, ser.validated_data)
        return Response(PositionReadSerializer(pos).data)

    def delete(self, request, pk: int):
        pos = get_position_by_id(pk)
        if not pos:
            return Response({"detail": "Position not found"}, status=status.HTTP_404_NOT_FOUND)
        delete_position(pos)
        return Response(status=status.HTTP_204_NO_CONTENT)