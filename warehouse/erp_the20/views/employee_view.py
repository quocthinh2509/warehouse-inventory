from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiParameter


from erp_the20.serializers.employee_serializer import EmployeeReadSerializer, EmployeeWriteSerializer
from erp_the20.services.employee_service import (
    create_employee,
    update_employee,
    delete_employee,
    activate_employee,
    deactivate_employee,
)
from erp_the20.selectors.employee_selector import (
    get_employee_by_id,
    list_all_employees,
    list_active_employees,
    get_employee_by_code,
    get_employee_by_user_name,
)
from .utils import extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors


# ==============================================================
# /api/employees/  -> GET list all + POST create
# ==============================================================
@extend_schema_view(
    get=extend_schema(
        tags=["Employee"],
        summary="List all employees / Lấy tất cả nhân viên",
        responses=OpenApiResponse(EmployeeReadSerializer(many=True)),
    ),
    post=extend_schema(
        tags=["Employee"],
        summary="Create employee / Tạo nhân viên",
        request=EmployeeWriteSerializer,               # Input
        responses={201: OpenApiResponse(EmployeeReadSerializer), **std_errors()},  # Output
    ),
)
class EmployeeListCreateView(APIView):
    """
    GET: Trả về danh sách tất cả nhân viên (cả active và inactive)
    POST: Tạo nhân viên mới, sử dụng service layer để xử lý business logic
    """

    def get(self, request):
        # 1. Lấy tất cả nhân viên từ selector
        employees = list_all_employees()
        # 2. Serialize dữ liệu để trả về API
        data = EmployeeReadSerializer(employees, many=True).data
        return Response(data)

    def post(self, request):
        # 1. Validate dữ liệu đầu vào với EmployeeWriteSerializer
        serializer = EmployeeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 2. Tạo nhân viên mới bằng service
        employee = create_employee(serializer.validated_data)

        # 3. Trả về dữ liệu employee theo ReadSerializer
        return Response(EmployeeReadSerializer(employee).data, status=status.HTTP_201_CREATED)


# ==============================================================
# /api/employees/<pk>/  -> GET detail + PUT update + DELETE
# ==============================================================
@extend_schema_view(
    get=extend_schema(
        tags=["Employee"],
        summary="Get employee details / Lấy thông tin nhân viên theo ID",
        parameters=[path_int("pk", "Employee ID")],
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    ),
    put=extend_schema(
        tags=["Employee"],
        summary="Update employee / Cập nhật nhân viên",
        parameters=[path_int("pk", "Employee ID")],
        request=EmployeeWriteSerializer,
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    ),
    delete=extend_schema(
        tags=["Employee"],
        summary="Delete employee / Xóa nhân viên",
        parameters=[path_int("pk", "Employee ID")],
        responses={204: OpenApiResponse(None, description="Deleted"), **std_errors()},
    ),
)
class EmployeeDetailView(APIView):
    """
    GET: Trả về chi tiết nhân viên theo ID
    PUT: Cập nhật thông tin nhân viên
    DELETE: Xóa nhân viên (hard delete)
    """

    def get(self, request, pk: int):
        employee = get_employee_by_id(pk)
        if not employee:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(EmployeeReadSerializer(employee).data)

    def put(self, request, pk: int):
        employee = get_employee_by_id(pk)
        if not employee:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        # Validate dữ liệu gửi lên
        serializer = EmployeeWriteSerializer(instance=employee, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)

        # Update employee qua service layer
        updated_employee = update_employee(employee, serializer.validated_data)

        return Response(EmployeeReadSerializer(updated_employee).data)

    def delete(self, request, pk: int):
        employee = get_employee_by_id(pk)
        if not employee:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        # Xóa nhân viên
        delete_employee(employee)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==============================================================
# /api/employees/<pk>/deactivate  -> POST
# ==============================================================
@extend_schema_view(
    post=extend_schema(
        tags=["Employee"],
        summary="Deactivate employee / Vô hiệu hóa nhân viên",
        parameters=[path_int("pk", "Employee ID")],
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    )
)
class EmployeeDeactivateView(APIView):
    """
    POST: Deactivate nhân viên (is_active=False)
    """

    def post(self, request, pk: int):
        employee = get_employee_by_id(pk)
        if not employee:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        employee = deactivate_employee(employee)
        return Response(EmployeeReadSerializer(employee).data)


# ==============================================================
# /api/employees/<pk>/activate  -> POST
# ==============================================================
@extend_schema_view(
    post=extend_schema(
        tags=["Employee"],
        summary="Activate employee / Kích hoạt nhân viên",
        parameters=[path_int("pk", "Employee ID")],
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    )
)
class EmployeeActivateView(APIView):
    """
    POST: Activate nhân viên (is_active=True)
    """

    def post(self, request, pk: int):
        employee = get_employee_by_id(pk)
        if not employee:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        employee = activate_employee(employee)
        return Response(EmployeeReadSerializer(employee).data)


# ==============================================================
# /api/employees/active/  -> GET
# ==============================================================
@extend_schema_view(
    get=extend_schema(
        tags=["Employee"],
        summary="List active employees / Danh sách nhân viên đang hoạt động",
        responses=OpenApiResponse(EmployeeReadSerializer(many=True)),
    )
)
class ActiveEmployeeListView(APIView):
    """
    GET: Trả về danh sách tất cả nhân viên đang hoạt động
    """

    def get(self, request):
        employees = list_active_employees()
        return Response(EmployeeReadSerializer(employees, many=True).data)




# ==============================================================
# /api/employees/<user_name>/  -> GET employee by user_name
# ==============================================================
@extend_schema_view(
    get=extend_schema(
        tags=["Employee"],
        summary="Get employee by user_name / Lấy nhân viên theo user_name",
        parameters=[OpenApiParameter(name="user_name", description="User Name", required=True, type=str)],
        responses={200: OpenApiResponse(EmployeeReadSerializer), **std_errors()},
    )
)
class EmployeeGetByUserNameView(APIView):
    """
    GET: Trả về chi tiết nhân viên theo user_name
    """

    def get(self, request, user_name: str):
        employee = get_employee_by_user_name(user_name)
        if not employee:
            return Response({"detail": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(EmployeeReadSerializer(employee).data)
