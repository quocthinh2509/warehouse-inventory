# views/department_views.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from erp_the20.serializers.department_serializer import DepartmentWriteSerializer, DepartmentReadSerializer
from erp_the20.services.department_service import create_department, update_department, delete_department
from erp_the20.selectors.department_selector import list_all_departments, get_department_by_id

from .utils import extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors

# -----------------------------
# /api/departments/  (list + create)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Department"],
        summary="List all departments",
        responses=OpenApiResponse(DepartmentReadSerializer(many=True))
    ),
    post=extend_schema(
        tags=["Department"],
        summary="Create a new department",
        request=DepartmentWriteSerializer,
        responses={201: OpenApiResponse(DepartmentReadSerializer), **std_errors()}
    )
)
class DepartmentListCreateView(APIView):
    def get(self, request):
        """
        Lấy danh sách tất cả Department, sắp xếp theo name.
        """
        departments = list_all_departments()
        data = DepartmentReadSerializer(departments, many=True).data
        return Response(data)

    def post(self, request):
        """
        Tạo mới một Department.
        Kiểm tra trùng code trước khi tạo.
        """
        ser = DepartmentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dept = create_department(ser.validated_data)
        return Response(DepartmentReadSerializer(dept).data, status=status.HTTP_201_CREATED)


# -----------------------------
# /api/departments/<pk>/  (get + update + delete)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Department"],
        summary="Get department details",
        parameters=[path_int("pk", "Department ID")],
        responses={200: OpenApiResponse(DepartmentReadSerializer), **std_errors()},
    ),
    put=extend_schema(
        tags=["Department"],
        summary="Update department (partial allowed)",
        parameters=[path_int("pk", "Department ID")],
        request=DepartmentWriteSerializer,
        responses={200: OpenApiResponse(DepartmentReadSerializer), **std_errors()},
    ),
    delete=extend_schema(
        tags=["Department"],
        summary="Delete department",
        parameters=[path_int("pk", "Department ID")],
        responses={204: OpenApiResponse(None, description="Deleted"), **std_errors()},
    ),
)
class DepartmentDetailView(APIView):
    def get(self, request, pk: int):
        dept = get_department_by_id(pk)
        if not dept:
            return Response({"detail": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(DepartmentReadSerializer(dept).data)

    def put(self, request, pk: int):
        dept = get_department_by_id(pk)
        if not dept:
            return Response({"detail": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = DepartmentWriteSerializer(dept, data=request.data, partial=True)  # partial=True cho phép cập nhật một phần
        ser.is_valid(raise_exception=True)
        updated = update_department(dept, ser.validated_data)
        return Response(DepartmentReadSerializer(updated).data)

    def delete(self, request, pk: int):
        dept = get_department_by_id(pk)
        if not dept:
            return Response({"detail": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        delete_department(dept)
        return Response(status=status.HTTP_204_NO_CONTENT)
