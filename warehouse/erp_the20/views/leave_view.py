from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from erp_the20.models import LeaveType, LeaveRequest, Employee
from erp_the20.serializers.leave_serializer import LeaveTypeSerializer, LeaveRequestSerializer
from erp_the20.services.leave_service import request_leave, approve_leave
from .utils import extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors, OpenApiExample

@extend_schema_view(
    get=extend_schema(tags=["Leave"], summary="List leave types",
                      responses=OpenApiResponse(LeaveTypeSerializer(many=True))),
    post=extend_schema(tags=["Leave"], summary="Create leave type",
                       request=LeaveTypeSerializer,
                       responses={201: OpenApiResponse(LeaveTypeSerializer), **std_errors()}),
)
class LeaveTypeListCreateView(APIView):
    def get(self, request):
        return Response(LeaveTypeSerializer(LeaveType.objects.all(), many=True).data)
    def post(self, request):
        ser = LeaveTypeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(LeaveTypeSerializer(obj).data, status=status.HTTP_201_CREATED)

@extend_schema_view(
    get=extend_schema(tags=["Leave"], summary="List leave requests",
                      responses=OpenApiResponse(LeaveRequestSerializer(many=True))),
    post=extend_schema(
        tags=["Leave"], summary="Create leave request",
        request=LeaveRequestSerializer,
        responses={201: OpenApiResponse(LeaveRequestSerializer), **std_errors()},
        examples=[
            OpenApiExample(
                "Body mẫu",
                request_only=True,
                value={
                    "employee": 1,
                    "leave_type": 2,
                    "start_date": "2025-09-20",
                    "end_date": "2025-09-22",
                    "hours": 16,
                    "reason": "Family",
                },
            )
        ],
    ),
)
class LeaveRequestListCreateView(APIView):
    def get(self, request):
        qs = LeaveRequest.objects.select_related("leave_type","employee").all()
        return Response(LeaveRequestSerializer(qs, many=True).data)
    def post(self, request):
        emp = Employee.objects.get(id=request.data["employee"])
        lt_id = request.data["leave_type"]
        from ..models import LeaveType
        lt = LeaveType.objects.get(id=lt_id)
        lr = request_leave(
            employee=emp, leave_type=lt,
            start_date=request.data["start_date"],
            end_date=request.data["end_date"],
            hours=request.data.get("hours"), reason=request.data.get("reason","")
        )
        return Response(LeaveRequestSerializer(lr).data, status=status.HTTP_201_CREATED)

@extend_schema_view(
    post=extend_schema(
        tags=["Leave"], summary="Approve leave request",
        parameters=[path_int("pk", "LeaveRequest ID")],
        responses={200: OpenApiResponse(LeaveRequestSerializer), **std_errors()},
    )
)
class LeaveApproveView(APIView):
    def post(self, request, pk: int):
        lr = approve_leave(leave_request_id=pk, approver=request.user)
        return Response(LeaveRequestSerializer(lr).data)
