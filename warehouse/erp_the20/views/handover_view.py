# -*- coding: utf-8 -*-
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from erp_the20.models import Handover
from erp_the20.serializers.handover_serializer import (
    HandoverSerializer, HandoverItemSerializer
)
from erp_the20.services import handover_service as svc


class HandoverViewSet(viewsets.ModelViewSet):
    """
    View chỉ điều phối request/response
    - Không gọi repository trực tiếp
    - Gọi service cho nghiệp vụ
    """
    queryset = Handover.objects.all().order_by("-created_at")
    serializer_class = HandoverSerializer

    def create(self, request, *args, **kwargs):
        d = request.data
        ho = svc.open_handover(
            employee_id=int(d["employee_id"]),
            manager_id=int(d["manager_id"]) if d.get("manager_id") else None,
            receiver_employee_id=int(d["receiver_employee_id"]) if d.get("receiver_employee_id") else None,
            due_date=d.get("due_date"),
            note=d.get("note", ""),
        )
        return Response(HandoverSerializer(ho).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        it = svc.add_item(
            int(pk),
            title=request.data["title"],
            detail=request.data.get("detail", ""),
            assignee_id=int(request.data["assignee_id"]) if request.data.get("assignee_id") else None,
        )
        return Response(HandoverItemSerializer(it).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)


class HandoverItemViewSet(viewsets.ViewSet):
    """Các thao tác trên Item đều đi qua service"""

    @action(detail=False, methods=["post"])
    def set_status(self, request):
        item_id = int(request.data["item_id"])
        status_val = int(request.data["status"])
        it = svc.set_item_status(item_id, status_val)
        return Response({"item_id": it.id, "status": it.status}, status=status.HTTP_200_OK)
