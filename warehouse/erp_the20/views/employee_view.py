from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from erp_the20.serializers.employee_serializer import (
    EmployeeReadSerializer,   # dùng cho RESPONSE
    EmployeeWriteSerializer,  # dùng cho REQUEST
)
from erp_the20.services.employee_service import (
    create_employee, deactivate_employee, activate_employee,
    update_employee, delete_employee
)
from erp_the20.selectors.employee_selector import (
    list_active_employees, get_employee_by_id, list_all_employees
)
from .utils import extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors


# -----------------------------
# /api/employees/  (GET list + POST create)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Employee"],
        summary="List all employees / Lấy tất cả nhân viên",
        responses=OpenApiResponse(EmployeeReadSerializer(many=True)),
    ),
    post=extend_schema(
        tags=["Employee"],
        summary="Create employee / Tạo nhân viên",
        request=EmployeeWriteSerializer,                               # <-- REQUEST = Write
        responses={201: OpenApiResponse(EmployeeReadSerializer),       # <-- RESPONSE = Read
                   **std_errors()},
    ),
)
class EmployeeListCreateView(APIView):
    """GET: danh sách nhân viên; POST: tạo nhân viên (qua service)."""

    def get(self, request):
        employees = list_all_employees()
        return Response(EmployeeReadSerializer(employees, many=True).data)

    def post(self, request):
        ser = EmployeeWriteSerializer(data=request.data)               # validate input theo *_id
        ser.is_valid(raise_exception=True)
        emp = create_employee(ser.validated_data)
        return Response(EmployeeReadSerializer(emp).data, status=status.HTTP_201_CREATED)


# -----------------------------
# /api/employees/<pk>/deactivate  (POST)
# -----------------------------
@extend_schema_view(
    post=extend_schema(
        tags=["Employee"],
        summary="Deactivate employee",
        parameters=[path_int("pk", "Employee ID")],
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    )
)
class EmployeeDeactivateView(APIView):
    """POST: deactivate nhân viên theo pk."""

    def post(self, request, pk: int):
        emp = get_employee_by_id(pk)
        if not emp:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        emp = deactivate_employee(emp)
        return Response(EmployeeReadSerializer(emp).data)


# -----------------------------
# /api/employees/<pk>/activate  (POST)
# -----------------------------
@extend_schema_view(
    post=extend_schema(
        tags=["Employee"],
        summary="Activate employee",
        parameters=[path_int("pk", "Employee ID")],
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    )
)
class EmployeeActivateView(APIView):
    """POST: activate nhân viên theo pk."""

    def post(self, request, pk: int):
        emp = get_employee_by_id(pk)
        if not emp:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        emp = activate_employee(emp)
        return Response(EmployeeReadSerializer(emp).data)


# -----------------------------
# /api/employees/<pk>/  (GET retrieve + PUT update + DELETE)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Employee"],
        summary="Get employee details",
        parameters=[path_int("pk", "Employee ID")],
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    ),
    put=extend_schema(
        tags=["Employee"],
        summary="Update employee",
        parameters=[path_int("pk", "Employee ID")],
        request=EmployeeWriteSerializer,                               # <-- REQUEST = Write
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},  # <-- RESPONSE = Read
    ),
    delete=extend_schema(
        tags=["Employee"],
        summary="Delete employee",
        parameters=[path_int("pk", "Employee ID")],
        responses={204: OpenApiResponse(None), **std_errors()},
    ),
)
class EmployeeDetailView(APIView):
    """GET: chi tiết; PUT: cập nhật; DELETE: xoá mềm/cứng tuỳ service."""

    def get(self, request, pk: int):
        emp = get_employee_by_id(pk)
        if not emp:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(EmployeeReadSerializer(emp).data)

    def put(self, request, pk: int):
        emp = get_employee_by_id(pk)
        if not emp:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        # dùng WriteSerializer để nhận *_id (department_id, position_id, default_worksite_id)
        ser = EmployeeWriteSerializer(data=request.data, partial=False)
        ser.is_valid(raise_exception=True)

        emp = update_employee(emp, ser.validated_data)
        return Response(EmployeeReadSerializer(emp).data)              # trả về Read

    def delete(self, request, pk: int):
        emp = get_employee_by_id(pk)
        if not emp:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        delete_employee(emp)
        return Response(status=status.HTTP_204_NO_CONTENT)


# -----------------------------
# /api/employees/active/  (GET)
# -----------------------------
@extend_schema_view(
    get=extend_schema(
        tags=["Employee"],
        summary="List active employees / Danh sách nhân viên đang hoạt động",
        responses=OpenApiResponse(EmployeeReadSerializer(many=True)),  # <-- RESPONSE = Read (many)
    ),
)
class ActiveEmployeeListView(APIView):
    """GET: trả danh sách tất cả nhân viên đang hoạt động."""

    def get(self, request):
        employees = list_active_employees()
        return Response(EmployeeReadSerializer(employees, many=True).data)
