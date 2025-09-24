from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from drf_spectacular.utils import OpenApiExample
# from rest_framework.permissions import IsAuthenticated  # nếu muốn bắt buộc login, bỏ comment và set ở class

from erp_the20.serializers.shift_serializer import (
    ShiftTemplateSerializer, ShiftInstanceSerializer, ShiftRegistrationSerializer,
    ShiftTemplateReadSerializer, ShiftInstanceReadSerializer, ShiftRegistrationReadSerializer, ShiftAssignmentReadSerializer,
    ShiftRegisterBodySerializer, ShiftDirectAssignBodySerializer, ShiftInstanceQuerySerializer
)
from erp_the20.selectors.shift_selector import (
    list_shift_templates, reload_shift_template,
    list_open_shift_instances, reload_shift_instance,
    get_active_employee, get_registration_with_related, get_assignment_with_related
)
from erp_the20.services.shift_service import register_shift, approve_registration, assign_shift
from .utils import (
    extend_schema, extend_schema_view, OpenApiResponse,
    q_date, q_int, path_int, std_errors
)

def user_or_none(user):
    """Trả về user nếu đã auth, ngược lại None (tránh AnonymousUser gán vào FK)."""
    return user if getattr(user, "is_authenticated", False) else None

# ---------- Shift Template ----------
@extend_schema_view(
    get=extend_schema(
        tags=["Shift"], summary="List shift templates",
        responses=OpenApiResponse(ShiftTemplateReadSerializer(many=True))
    ),
    post=extend_schema(
        tags=["Shift"], summary="Create shift template",
        request=ShiftTemplateSerializer,
        responses={201: OpenApiResponse(ShiftTemplateReadSerializer), **std_errors()},
    ),
)
class ShiftTemplateListCreateView(APIView):
    # permission_classes = [IsAuthenticated]  # tuỳ chính sách
    def get(self, request):
        qs = list_shift_templates()
        return Response(ShiftTemplateReadSerializer(qs, many=True).data)

    def post(self, request):
        ser = ShiftTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        obj = reload_shift_template(obj.pk)
        return Response(ShiftTemplateReadSerializer(obj).data, status=status.HTTP_201_CREATED)

# ---------- Shift Instance ----------
@extend_schema_view(
    get=extend_schema(
        tags=["Shift"], summary="List shift instances",
        parameters=[q_date("date_from", "YYYY-MM-DD"), q_date("date_to", "YYYY-MM-DD"), q_int("worksite", "Worksite ID")],
        responses=OpenApiResponse(ShiftInstanceReadSerializer(many=True)),
        examples=[OpenApiExample("Query ví dụ", value={"date_from": "2025-09-01", "date_to": "2025-09-30", "worksite": 1})],
    ),
    post=extend_schema(
        tags=["Shift"], summary="Create shift instance",
        request=ShiftInstanceSerializer,
        responses={201: OpenApiResponse(ShiftInstanceReadSerializer), **std_errors()},
    ),
)
class ShiftInstanceListCreateView(APIView):
    # permission_classes = [IsAuthenticated]
    def get(self, request):
        qser = ShiftInstanceQuerySerializer(data=request.query_params)
        qser.is_valid(raise_exception=True)
        p = qser.validated_data

        qs = list_open_shift_instances(
            date_from=p.get("date_from"),
            date_to=p.get("date_to"),
            worksite_id=p.get("worksite")
        )
        return Response(ShiftInstanceReadSerializer(qs, many=True).data)

    def post(self, request):
        ser = ShiftInstanceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        obj = reload_shift_instance(obj.pk)
        return Response(ShiftInstanceReadSerializer(obj).data, status=status.HTTP_201_CREATED)

# ---------- Register a shift ----------
@extend_schema_view(
    post=extend_schema(
        tags=["Shift"], summary="Register to a shift instance",
        parameters=[path_int("shift_id", "ShiftInstance ID")],
        request=ShiftRegisterBodySerializer,
        responses={201: OpenApiResponse(ShiftRegistrationReadSerializer), **std_errors()},
        examples=[OpenApiExample("Body mẫu", request_only=True, value={"employee": 7, "reason": "swap"})],
    )
)
class ShiftRegisterView(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self, request, shift_id: int):
        body = ShiftRegisterBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        emp_id = body.validated_data["employee"]
        reason = body.validated_data.get("reason", "")

        employee = get_active_employee(emp_id)
        if not employee:
            raise DRFValidationError({"employee": "Employee not found or inactive."})

        try:
            reg = register_shift(
                employee=employee,
                shift_instance_id=shift_id,
                created_by=user_or_none(request.user),  # <<< rửa user
                reason=reason,
            )
        except Exception as exc:
            if hasattr(exc, "message_dict"):
                raise DRFValidationError(exc.message_dict)
            raise DRFValidationError({"detail": str(exc)})

        reg = get_registration_with_related(reg.pk)
        return Response(ShiftRegistrationReadSerializer(reg).data, status=status.HTTP_201_CREATED)

# ---------- Approve a registration ----------
@extend_schema_view(
    post=extend_schema(
        tags=["Shift"], summary="Approve a shift registration",
        parameters=[path_int("reg_id", "Registration ID")],
        responses={200: OpenApiResponse(ShiftRegistrationReadSerializer), **std_errors()},
    )
)
class ShiftApproveRegistrationView(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self, request, reg_id: int):
        try:
            reg = approve_registration(
                registration_id=reg_id,
                approver=user_or_none(request.user),  # <<< rửa user
            )
        except Exception as exc:
            if hasattr(exc, "message_dict"):
                raise DRFValidationError(exc.message_dict)
            raise DRFValidationError({"detail": str(exc)})

        reg = get_registration_with_related(reg.pk)
        return Response(ShiftRegistrationReadSerializer(reg).data)

# ---------- Direct assign ----------
@extend_schema_view(
    post=extend_schema(
        tags=["Shift"], summary="Directly assign an employee to a shift instance",
        parameters=[path_int("shift_id", "ShiftInstance ID")],
        request=ShiftDirectAssignBodySerializer,
        responses={201: OpenApiResponse(ShiftAssignmentReadSerializer), **std_errors()},
        examples=[OpenApiExample("Body mẫu", request_only=True, value={"employee": 1})],
    )
)
class ShiftDirectAssignView(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self, request, shift_id: int):
        body = ShiftDirectAssignBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        emp_id = body.validated_data["employee"]

        employee = get_active_employee(emp_id)
        if not employee:
            raise DRFValidationError({"employee": "Employee not found or inactive."})

        try:
            ass = assign_shift(
                employee=employee,
                shift_instance_id=shift_id,
                assigned_by=user_or_none(request.user),  # <<< rửa user
            )
        except Exception as exc:
            if hasattr(exc, "message_dict"):
                raise DRFValidationError(exc.message_dict)
            raise DRFValidationError({"detail": str(exc)})

        ass = get_assignment_with_related(ass.pk)
        return Response(ShiftAssignmentReadSerializer(ass).data, status=status.HTTP_201_CREATED)
