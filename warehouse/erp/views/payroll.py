
# ─────────────────────────────────────────────────────────────
# erp/views/payroll.py
# ─────────────────────────────────────────────────────────────
from rest_framework import viewsets, permissions, views
from rest_framework.response import Response
from erp.models import PayrollPeriod, PayrollLine
from erp.serializers.payroll import PayrollPeriodSerializer, PayrollLineSerializer, PayrollPreviewSerializer

class PayrollPeriodViewSet(viewsets.ModelViewSet):
    queryset = PayrollPeriod.objects.all().order_by('-start_date')
    serializer_class = PayrollPeriodSerializer
    permission_classes = [permissions.AllowAny]

class PayrollLineViewSet(viewsets.ModelViewSet):
    queryset = PayrollLine.objects.all().order_by('-id')
    serializer_class = PayrollLineSerializer
    permission_classes = [permissions.AllowAny]

class PayrollPreviewView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        ser = PayrollPreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.save()
        return Response({'results': data})
