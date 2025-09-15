from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny

from .models import CheckEvent
from .serializers import CheckEventSerializer

# --- PAGE: trang test GPS ---
@require_GET
def test_page(request):
    # cấp sẵn csrf token cho form nếu bạn muốn dùng sau này (ở đây API không cần)
    get_token(request)
    return render(request, "checks/test.html", {})

# --- API: ghi check-in/out ---
class CheckCreateView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        # Lấy IP và UA
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR"))
        ua = request.META.get("HTTP_USER_AGENT","")

        # Gắn vào payload trước khi validate
        data = {**data, "ip": ip, "ua": ua}
        ser = CheckEventSerializer(data=data)
        if ser.is_valid():
            obj = CheckEvent.objects.create(
                type=ser.validated_data["type"],
                lat=ser.validated_data["lat"],
                lng=ser.validated_data["lng"],
                accuracy=ser.validated_data.get("accuracy"),
                note=ser.validated_data.get("note",""),
                ip=ip, ua=ua,
            )
            out = CheckEventSerializer(obj).data
            return Response(out, status=201)
        return Response({"detail":"invalid", "errors": ser.errors}, status=400)

# --- API: xem 20 bản ghi gần nhất ---
class CheckRecentView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        qs = CheckEvent.objects.all()[:20]
        return Response(CheckEventSerializer(qs, many=True).data)
