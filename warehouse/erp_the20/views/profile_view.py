# erp_the20/views/profile_view.py
from rest_framework import status, viewsets
from rest_framework.response import Response
from erp_the20.serializers.profile_serializer import EmployeeProfileSerializer
from erp_the20.services import profile_service as svc
from erp_the20.repositories import profile_repository as repo

class EmployeeProfileViewSet(viewsets.ViewSet):
    # GET /the20/profile/?q=&page=&page_size=
    def list(self, request):
        q = request.query_params.get("q") or None
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))
        page = max(page, 1)
        page_size = max(min(page_size, 200), 1)

        offset = (page - 1) * page_size
        total, items = repo.list_profiles(q=q, limit=page_size, offset=offset)
        data = EmployeeProfileSerializer(items, many=True).data
        return Response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": data
        }, status=status.HTTP_200_OK)

    # GET /the20/profile/{user_id}/
    def retrieve(self, request, pk=None):
        obj = repo.get_or_create(int(pk))
        return Response(EmployeeProfileSerializer(obj).data)

    # PUT /the20/profile/{user_id}/
    def update(self, request, pk=None):
        obj = svc.upsert(int(pk), request.data)
        return Response(EmployeeProfileSerializer(obj).data, status=status.HTTP_200_OK)
