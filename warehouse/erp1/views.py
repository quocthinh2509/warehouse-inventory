from datetime import timedelta
from django.utils import timezone
from django.db.models import Min, Max
from django.shortcuts import render
from rest_framework import viewsets, mixins, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny  # đổi thành IsAuthenticated khi dùng thật
from rest_framework.decorators import action
from .models import *
from .serializers import *
from .utils import haversine_distance_m

# ===== CRUD cơ bản =====
class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all().order_by("-id")
    serializer_class = EmployeeSerializer
    permission_classes = [AllowAny]

class WorksiteViewSet(viewsets.ModelViewSet):
    queryset = Worksite.objects.all().order_by("code")
    serializer_class = WorksiteSerializer
    permission_classes = [AllowAny]

class ShiftTemplateViewSet(viewsets.ModelViewSet):
    queryset = ShiftTemplate.objects.all().order_by("code")
    serializer_class = ShiftTemplateSerializer
    permission_classes = [AllowAny]

class ShiftPlanViewSet(viewsets.ModelViewSet):
    queryset = ShiftPlan.objects.select_related("employee","template").all().order_by("-date")
    serializer_class = ShiftPlanSerializer
    permission_classes = [AllowAny]

class LeaveTypeViewSet(viewsets.ModelViewSet):
    queryset = LeaveType.objects.all().order_by("code")
    serializer_class = LeaveTypeSerializer
    permission_classes = [AllowAny]

class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related("employee","leave_type").all().order_by("-id")
    serializer_class = LeaveRequestSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        obj = self.get_object()
        if obj.status != "pending":
            return Response({"detail":"Không ở trạng thái pending."}, status=400)
        # (demo) set approver = employee đầu tiên
        approver = Employee.objects.first()
        obj.status = "approved"; obj.approver = approver; obj.save(update_fields=["status","approver"])
        return Response({"detail":"Đã duyệt."})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        obj = self.get_object()
        if obj.status != "pending":
            return Response({"detail":"Không ở trạng thái pending."}, status=400)
        obj.status = "rejected"; obj.save(update_fields=["status"])
        return Response({"detail":"Đã từ chối."})

class ShiftRegistrationViewSet(viewsets.ModelViewSet):
    queryset = ShiftRegistration.objects.select_related("employee","template").all().order_by("-id")
    serializer_class = ShiftRegistrationSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        reg = self.get_object()
        if reg.status != "pending":
            return Response({"detail":"Không ở trạng thái pending."}, status=400)
        reg.status = "approved"; reg.save(update_fields=["status"])
        # Áp vào ShiftPlan
        plan, _ = ShiftPlan.objects.update_or_create(
            employee=reg.employee, date=reg.date, slot=reg.slot,
            defaults={"template": reg.template, "status":"approved"}
        )
        return Response({"detail":"Đã duyệt & cập nhật kế hoạch ca.", "plan_id": plan.id})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        reg = self.get_object()
        if reg.status != "pending":
            return Response({"detail":"Không ở trạng thái pending."}, status=400)
        reg.status = "rejected"; reg.save(update_fields=["status"])
        return Response({"detail":"Đã từ chối."})

class AttendanceLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AttendanceLog.objects.select_related("employee","worksite").all().order_by("-occurred_at")
    serializer_class = AttendanceLogSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        qs = super().get_queryset()
        emp = self.request.query_params.get("employee_id")
        dfrom = self.request.query_params.get("date_from")
        dto = self.request.query_params.get("date_to")
        typ = self.request.query_params.get("type")
        if emp: qs = qs.filter(employee_id=emp)
        if typ in ("IN","OUT"): qs = qs.filter(type=typ)
        if dfrom: qs = qs.filter(occurred_at__date__gte=dfrom)
        if dto: qs = qs.filter(occurred_at__date__lte=dto)
        return qs

# ===== Check-in/out =====
class AttendanceCheckView(APIView):
    permission_classes = [AllowAny]
    DUP_WINDOW_MIN = 3
    MIN_REQUIRED_ACCURACY = 200
    EXTRA_TOLERANCE = 50
    GRACE_BEFORE_MIN = 15
    GRACE_AFTER_MIN = 30

    def _resolve_shift_plan(self, emp, now):
        tz = timezone.get_current_timezone()
        today = now.date(); yest = today - timedelta(days=1)
        plans = list(ShiftPlan.objects.filter(employee=emp, date__in=[yest,today]).select_related("template"))
        windowed=[]
        for p in plans:
            s = p.start_dt(tz) - timedelta(minutes=self.GRACE_BEFORE_MIN)
            e = p.end_dt(tz) + timedelta(minutes=self.GRACE_AFTER_MIN)
            if s <= now <= e:
                center = s + (e - s)/2
                windowed.append((abs((now - center).total_seconds()), p))
        if not windowed: return None
        windowed.sort(key=lambda x:x[0])
        return windowed[0][1]

    def post(self, request):
        ser = AttendanceCheckSerializer(data=request.data); ser.is_valid(raise_exception=True)
        data = ser.validated_data
        employee_id = data["employee_id"]; typ = data["type"]
        lat = data.get("lat"); lng = data.get("lng"); accuracy_m = data.get("accuracy_m")
        device_id = data.get("device_id") or ""; note = data.get("note") or ""
        worksite = None

        try:
            emp = Employee.objects.get(id=employee_id, is_active=True)
        except Employee.DoesNotExist:
            return Response({"detail":"Employee không tồn tại/không active."}, status=400)

        worksite_id = data.get("worksite_id")
        if worksite_id:
            try:
                worksite = Worksite.objects.get(id=worksite_id)
            except Worksite.DoesNotExist:
                return Response({"detail":"Worksite không tồn tại."}, status=400)

        now = timezone.now()
        # chống trùng
        window_start = now - timedelta(minutes=self.DUP_WINDOW_MIN)
        dup = AttendanceLog.objects.filter(employee=emp, type=typ, occurred_at__gte=window_start).first()
        if dup:
            return Response({"detail": f"Đã {('check-in' if typ=='IN' else 'check-out')} trong {self.DUP_WINDOW_MIN} phút.",
                             "last_event": AttendanceLogSerializer(dup).data}, status=409)

        # geofence
        is_valid=True; invalid_reason=""; distance_m=None
        if worksite and (lat is not None and lng is not None):
            distance_m = haversine_distance_m(lat,lng,worksite.lat,worksite.lng)
            if accuracy_m is not None and accuracy_m > self.MIN_REQUIRED_ACCURACY:
                is_valid=False; invalid_reason=f"Độ chính xác vị trí thấp (> {self.MIN_REQUIRED_ACCURACY}m): {accuracy_m}m."
            elif distance_m is not None and distance_m > (worksite.radius_m + self.EXTRA_TOLERANCE + (accuracy_m or 0)):
                is_valid=False; invalid_reason=f"Ngoài geofence: cách {distance_m}m, bán kính {worksite.radius_m}m."

        plan = self._resolve_shift_plan(emp, now)

        if not is_valid:
            return Response({"detail":"Sự kiện không hợp lệ.","invalid_reason":invalid_reason,"distance_m":distance_m}, status=400)

        log = AttendanceLog.objects.create(
            employee=emp, worksite=worksite, shift_plan=plan, type=typ, occurred_at=now,
            lat=lat, lng=lng, accuracy_m=accuracy_m, distance_m=distance_m,
            source="web", device_id=device_id, note=note, is_valid=True, invalid_reason=""
        )

        # summary giản lược theo ngày
        today = now.date()
        qs = AttendanceLog.objects.filter(employee=emp, occurred_at__date=today).order_by("occurred_at")
        first_in = qs.filter(type="IN").aggregate(t=Min("occurred_at"))["t"]
        last_out = qs.filter(type="OUT").aggregate(t=Max("occurred_at"))["t"]

        # tính tổng phút (pair đơn giản)
        total_minutes=0; in_stack=[]
        for e in qs:
            if e.type=="IN": in_stack.append(e.occurred_at)
            elif e.type=="OUT" and in_stack:
                t_in = in_stack.pop(0)
                diff = (e.occurred_at - t_in).total_seconds()//60
                if diff>0: total_minutes += int(diff)

        return Response({
            "detail":"OK",
            "saved": AttendanceLogSerializer(log).data,
            "summary": {"date": str(today), "first_in": first_in, "last_out": last_out, "total_minutes": total_minutes},
            "saved_plan": ({
                "id": log.shift_plan_id,
                "date": str(log.shift_plan.date),
                "slot": log.shift_plan.slot,
                "template": log.shift_plan.template.code
            } if log.shift_plan_id else None)
        })

# ===== Timesheet: tổng hợp lại theo ca (đơn giản, để chạy ngay) =====
class TimesheetGenerateView(APIView):
    permission_classes = [AllowAny]
    """
    POST /api/timesheet/generate { "date_from":"YYYY-MM-DD", "date_to":"YYYY-MM-DD", "employee_id": (optional) }
    """
    def post(self, request):
        dfrom = request.data.get("date_from"); dto = request.data.get("date_to")
        emp_id = request.data.get("employee_id")
        if not dfrom or not dto: return Response({"detail":"Thiếu date_from/date_to."}, status=400)

        q_logs = AttendanceLog.objects.filter(occurred_at__date__gte=dfrom, occurred_at__date__lte=dto, is_valid=True)
        if emp_id: q_logs = q_logs.filter(employee_id=emp_id)

        # gom theo employee+date+slot (nếu có shift_plan, ưu tiên dùng slot; nếu không, slot=1)
        from collections import defaultdict
        buckets = defaultdict(list)
        for log in q_logs.order_by("employee_id","occurred_at"):
            key = (log.employee_id, log.occurred_at.date(), log.shift_plan.slot if log.shift_plan_id else 1, log.shift_plan_id or None)
            buckets[key].append(log)

        created, updated = 0, 0
        for (emp_id, d, slot, plan_id), rows in buckets.items():
            minutes = 0; stack=[]
            for r in rows:
                if r.type=="IN": stack.append(r.occurred_at)
                elif r.type=="OUT" and stack:
                    t_in = stack.pop(0)
                    diff = (r.occurred_at - t_in).total_seconds()//60
                    if diff>0: minutes += int(diff)
            obj, is_created = TimesheetEntry.objects.update_or_create(
                employee_id=emp_id, date=d, slot=slot,
                defaults={"shift_plan_id": plan_id, "minutes_worked": minutes}
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        return Response({"detail":"OK","created":created,"updated":updated})

# ===== Payroll: demo tính nhanh (preview) =====
class PayrollPreviewView(APIView):
    permission_classes = [AllowAny]
    """
    GET /api/payroll/preview?period=YYYY-MM&employee_id=1
    Tính: base theo (minutes_worked / (std_days*std_minutes)) * base_salary
    """
    def get(self, request):
        period = request.GET.get("period"); emp_id = request.GET.get("employee_id")
        if not (period and emp_id): return Response({"detail":"Thiếu period/employee_id."}, status=400)
        try:
            setting = PayrollSetting.objects.get(period=period)
        except PayrollSetting.DoesNotExist:
            return Response({"detail":"Chưa có PayrollSetting cho period."}, status=400)

        # lấy toàn bộ timesheet của period
        from datetime import datetime as dt
        y, m = map(int, period.split("-"))
        from calendar import monthrange
        first = dt(y,m,1).date(); last = first.replace(day=monthrange(y,m)[1])

        q = TimesheetEntry.objects.filter(employee_id=emp_id, date__gte=first, date__lte=last)
        total_minutes = sum(e.minutes_worked for e in q)
        std_total = float(setting.std_working_days) * setting.std_minutes_per_day

        emp = Employee.objects.get(id=emp_id)
        base = (Decimal(total_minutes) / Decimal(std_total) * emp.base_salary).quantize(Decimal("0.01"))

        return Response({
            "employee": EmployeeSerializer(emp).data,
            "period": period,
            "total_minutes": total_minutes,
            "std_minutes": int(std_total),
            "base_salary": str(emp.base_salary),
            "base_pay_calc": str(base),
        })

# ===== HTML demo pages =====
def check_page(request):  return render(request, "erp/check.html")
def leave_page(request):  return render(request, "erp/leave.html")
def shiftreg_page(request): return render(request, "erp/shiftreg.html")
def timesheet_page(request): return render(request, "erp/timesheet.html")
