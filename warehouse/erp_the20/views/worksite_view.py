from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from erp_the20.serializers.worksite_serializer import WorksiteReadSerializer, WorksiteWriteSerializer
from erp_the20.services.worksite_service import create_worksite, deactivate_worksite, activate_worksite, update_worksite, delete_worksite
from erp_the20.selectors.worksite_selector import list_active_worksites, get_worksite_by_id, list_all_worksites
from .utils import extend_schema, extend_schema_view, OpenApiResponse, path_int, std_errors

@extend_schema_view(
    get=extend_schema(tags=["Worksite"], summary="List all worksites",
                      responses=OpenApiResponse(WorksiteReadSerializer(many=True))),
    post=extend_schema(tags=["Worksite"], summary="Create worksite",
                       request=WorksiteWriteSerializer,
                       responses={201: OpenApiResponse(WorksiteReadSerializer), **std_errors()}),
)
class WorksiteListCreateView(APIView):
    def get(self, request):
        worksites = list_all_worksites()
        data = WorksiteReadSerializer(worksites, many=True).data
        return Response(data)

    def post(self, request):
        ser = WorksiteWWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = create_worksite(ser.validated_data)
        return Response(WorksiteReadSerializer(ws).data, status=status.HTTP_201_CREATED)

@extend_schema_view(
    post=extend_schema(
        tags=["Worksite"], summary="Deactivate worksite",
        parameters=[path_int("pk", "Worksite ID")],
        responses={200: OpenApiResponse(WorksiteReadSerializer), **std_errors()},
    )
)
class WorksiteDeactivateView(APIView):
    def post(self, request, pk: int):
        ws = get_worksite_by_id(pk)
        if not ws:
            return Response({"detail": "Worksite not found"}, status=status.HTTP_404_NOT_FOUND)
        ws = deactivate_worksite(ws)
        return Response(WorksiteReadSerializer(ws).data)


@extend_schema_view(
    get=extend_schema(
        tags=["Worksite"], summary="Get worksite by ID",
        parameters=[path_int("pk", "Worksite ID")],
        responses={200: OpenApiResponse(WorksiteReadSerializer), **std_errors()},
    ),
    put=extend_schema(
        tags=["Worksite"], summary="Update worksite",
        parameters=[path_int("pk", "Worksite ID")],
        request=WorksiteWriteSerializer,
        responses={200: OpenApiResponse(WorksiteReadSerializer), **std_errors()},
    ),
    delete=extend_schema(
        tags=["Worksite"], summary="Delete worksite",
        parameters=[path_int("pk", "Worksite ID")],
        responses={204: OpenApiResponse(description="No Content"), **std_errors()},
    ),
)
class WorksiteDetailView(APIView):
    def get(self, request, pk: int):
        ws = get_worksite_by_id(pk)
        if not ws:
            return Response({"detail": "Worksite not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(WorksiteReadSerializer(ws).data)

    def put(self, request, pk: int):
        ws = get_worksite_by_id(pk)
        if not ws:
            return Response({"detail": "Worksite not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = WorksiteWriteSerializer(ws, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ws = update_worksite(ws, ser.validated_data)
        return Response(WorksiteReadSerializer(ws).data)

    def delete(self, request, pk: int):
        ws = get_worksite_by_id(pk)
        if not ws:
            return Response({"detail": "Worksite not found"}, status=status.HTTP_404_NOT_FOUND)
        delete_worksite(ws)
        return Response(status=status.HTTP_204_NO_CONTENT)

@extend_schema_view(
    post=extend_schema(
        tags=["Worksite"], summary="Activate worksite",
        parameters=[path_int("pk", "Worksite ID")],
        responses={200: OpenApiResponse(WorksiteReadSerializer), **std_errors()},
    )
)
class WorksiteActivateView(APIView):
    def post(self, request, pk: int):
        ws = get_worksite_by_id(pk)
        if not ws:
            return Response({"detail": "Worksite not found"}, status=status.HTTP_404_NOT_FOUND)
        ws = activate_worksite(ws)
        return Response(WorksiteReadSerializer(ws).data)


class ActiveWorksiteListView(APIView):
    @extend_schema(
        tags=["Worksite"], summary="List active worksites, lấy tất cả chổ làm hiệc đang hoạt động",
        responses=OpenApiResponse(WorksiteReadSerializer(many=True)),
    )
    def get(self, request):
        worksites = list_active_worksites()
        data = WorksiteReadSerializer(worksites, many=True).data
        return Response(data)

