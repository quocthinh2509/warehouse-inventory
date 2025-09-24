from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from erp_the20.serializers.department_serializer import DepartmentReadSerializer, DepartmentWriteSerializer
from erp_the20.services.department_service import create_department, deactivate_department, update_department, activate_department, delete_department
from erp_the20.selectors.department_selector import list_active_departments, get_department_by_id, list_all_departments
from .utils import (
    extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors
)


@extend_schema_view(
    get=extend_schema(tags=["Department"], summary="List all departments",
                      responses=OpenApiResponse(DepartmentReadSerializer(many=True))),
    post=extend_schema(tags=["Department"], summary="Create department",
                       request=DepartmentWriteSerializer,
                       responses={201: OpenApiResponse(DepartmentReadSerializer), **std_errors()}),
)
class DepartmentListCreateView(APIView):
    def get(self, request): # lấy tất cả phòng ban
        departments = list_all_departments()
        data = DepartmentReadSerializer(departments, many=True).data
        return Response(data)

    def post(self, request):
        ser = DepartmentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dept = create_department(ser.validated_data)
        return Response(DepartmentReadSerializer(dept).data, status=status.HTTP_201_CREATED)

@extend_schema_view(
    post=extend_schema(
        tags=["Department"], summary="Deactivate department",
        parameters=[path_int("pk", "Department ID")],
        responses={200: OpenApiResponse(DepartmentReadSerializer), **std_errors()},
    )
)
class DepartmentDeactivateView(APIView):
    def post(self, request, pk: int):
        dept = get_department_by_id(pk)
        if not dept:
            return Response({"detail": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        dept = deactivate_department(dept)
        return Response(DepartmentReadSerializer(dept).data)


# -----------------------------
# /api/departments/<pk>/activate  (activate)
# -----------------------------
@extend_schema_view(
    post=extend_schema(
        tags=["Department"], summary="Activate department",
        parameters=[path_int("pk", "Department ID")],
        responses={200: OpenApiResponse(DepartmentReadSerializer), **std_errors()},
    )
)
class DepartmentActivateView(APIView):
    def post(self, request, pk: int):
        dept = get_department_by_id(pk)
        if not dept:
            return Response({"detail": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        dept = activate_department(dept)
        return Response(DepartmentReadSerializer(dept).data)

# -----------------------------
# /api/departments/<pk>/  (get + update + delete)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Department"], summary="Get department details",
        parameters=[path_int("pk", "Department ID")],
        responses={200: OpenApiResponse(DepartmentReadSerializer), **std_errors()},
    ),
    put=extend_schema(
        tags=["Department"], summary="Update department (replace/partial allowed)",
        parameters=[path_int("pk", "Department ID")],
        request=DepartmentWriteSerializer,
        responses={200: OpenApiResponse(DepartmentReadSerializer), **std_errors()},
    ),
    delete=extend_schema(
        tags=["Department"], summary="Delete department",
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
        ser = DepartmentWriteSerializer(dept, data=request.data, partial=True)  # cho phép partial
        ser.is_valid(raise_exception=True)
        updated = update_department(dept, ser.validated_data)  # dùng service update của bạn
        return Response(DepartmentReadSerializer(updated).data)

    def delete(self, request, pk: int):
        dept = get_department_by_id(pk)
        if not dept:
            return Response({"detail": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        delete_department(dept)  # service thực hiện xoá hẳn (hoặc soft-delete tuỳ bạn)
        return Response(status=status.HTTP_204_NO_CONTENT)


