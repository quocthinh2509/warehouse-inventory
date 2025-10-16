from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from erp_the20.models import Proposal
from erp_the20.serializers.proposal_serializer import ProposalSerializer
from erp_the20.services import proposal_service as svc

def _to_bool(v):
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.strip().lower() in ("1","true","yes","y","on")
    if isinstance(v, (int,float)): return bool(v)
    return False

class ProposalViewSet(viewsets.ModelViewSet):
    queryset = Proposal.objects.all().order_by("-created_at")
    serializer_class = ProposalSerializer

    def create(self, request, *args, **kwargs):
        d = request.data
        p = svc.submit(
            employee_id=int(d["employee_id"]),
            type=int(d["type"]),
            title=d["title"],
            content=d.get("content",""),
            manager_id=int(d["manager_id"]) if d.get("manager_id") else None,
            # NEW flags (mặc định: email=True, lark=False)
            send_email=_to_bool(d.get("send_email", True)),
            send_lark=_to_bool(d.get("send_lark", False)),
        )
        return Response(ProposalSerializer(p).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        note = request.data.get("note","")
        with transaction.atomic():
            p = svc.approve(int(pk), note)
        return Response(ProposalSerializer(p).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        note = request.data.get("note","")
        with transaction.atomic():
            p = svc.reject(int(pk), note)
        return Response(ProposalSerializer(p).data)

    @action(detail=True, methods=["post"])
    def set_note(self, request, pk=None):
        note = request.data.get("note","")
        with transaction.atomic():
            p = svc.set_decision_note(int(pk), note)
        return Response(ProposalSerializer(p).data)
