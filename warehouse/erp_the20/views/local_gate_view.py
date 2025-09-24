# erp_the20/views/local_gate_view.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError

from erp_the20.serializers.local_gate_serializer import AttestationProofSerializer
from erp_the20.services.local_gate_service import verify_attestation_and_issue_token
from .utils import extend_schema, extend_schema_view, OpenApiResponse, std_errors

@extend_schema_view(
    post=extend_schema(
        tags=["WiFi Gate"],
        summary="Đổi attestation từ Agent thành local_access_token",
        description="Xác thực HMAC + purpose + exp, sau đó trả JWT sống ngắn để dùng cho check-in/out.",
        request=AttestationProofSerializer,
        responses={200: OpenApiResponse(dict, description="{'ok': true, 'local_access_token': '<JWT>'}"), **std_errors()},
    )
)
class LocalVerifyView(APIView):
    authentication_classes = []  # demo: mở (prod: rate-limit/IP allowlist)
    permission_classes = []

    def post(self, request):
        ser = AttestationProofSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            token = verify_attestation_and_issue_token(data["attestation"], data["sig"])
        except Exception as exc:
            raise DRFValidationError({"detail": str(exc)})
        return Response({"ok": True, "local_access_token": token})
