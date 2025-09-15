# views.py
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
import csv
from rest_framework.parsers import JSONParser

from .models import Department, Employee, Worksite, Attendance, EmployeeWorksite
from .serializers import (
    DepartmentSerializer, EmployeeSerializer, WorksiteSerializer, AttendanceSerializer, EmployeeWorksiteSerializer,
)
from .utils import nearest_allowed_worksite  # <<< dùng hàm bạn đã có

# --- helper: lấy IP thật (qua proxy) ---
def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# ==========================
# 1) TẠO BẢN GHI CHẤM CÔNG
# ==========================
class AttendanceCreateView(APIView):
    """
    POST /api/attend/check
    Body:
    {
      "employee_id": 12,
      "type": "IN" | "OUT",
      "lat": 10.8345,
      "lng": 106.7010,
      "accuracy": 22,        # mét (optional)
      "note": "đi làm",
      "source": "web"
    }
    """
    permission_classes = [permissions.AllowAny]
    ACCURACY_THRESHOLD = 100  # mét

    def post(self, request):
        # 1) Validate input (map *_id -> instance)
        ser_in = AttendanceSerializer(data=request.data)
        ser_in.is_valid(raise_exception=True)
        v = ser_in.validated_data

        emp = v["employee"]
        typ = v["type"]
        lat, lng = v["lat"], v["lng"]
        accuracy = v.get("accuracy")

        # 2) Accuracy check -> lỗi 400, không lưu
        if accuracy is not None and accuracy > self.ACCURACY_THRESHOLD:
            return Response({
                "code": "low_accuracy",
                "detail": "Vị trí không đủ chính xác.",
                "accuracy": accuracy,
                "threshold": self.ACCURACY_THRESHOLD
            }, status=400)

        # 3) Geofence: tìm worksite gần nhất được phép
        ws, distance_m = nearest_allowed_worksite(emp, lat, lng)

        # Ngoài vùng chấm công -> lỗi 403, không lưu (nếu bạn muốn vẫn lưu log, bỏ đoạn return này)
        if not ws or distance_m is None or distance_m > ws.radius_m:
            return Response({
                "code": "out_of_geofence",
                "detail": "Ngoài vùng chấm công cho phép.",
                "distance_m": distance_m,
                "radius_m": (ws.radius_m if ws else None),
            }, status=403)

        # 4) Chống duplicate trong ngày (không lưu nếu trùng) -> lỗi 409
        today = timezone.localdate()
        last = (Attendance.objects
                .filter(employee=emp, local_date=today)
                .order_by("-ts")
                .first())

        dup_reason = None
        if typ == "IN":
            if last and last.type == "IN":
                dup_reason = "Bạn đã IN trong hôm nay."
        else:  # OUT
            if not last or last.type != "IN":
                dup_reason = "Chưa IN trước khi OUT."

        if dup_reason:
            return Response({
                "code": "duplicate",
                "detail": dup_reason
            }, status=409)

        # 5) Hợp lệ -> lưu DB
        att = Attendance.objects.create(
            employee=emp, worksite=ws, type=typ,
            lat=lat, lng=lng, accuracy=accuracy, distance_m=int(distance_m),
            status="accepted",
            note=v.get("note", ""), source=v.get("source", "web"),
            ip=get_client_ip(request),
            ua=request.META.get("HTTP_USER_AGENT", ""),
        )

        return Response(AttendanceSerializer(att).data, status=201)

# ==========================
# 2) LIST LOG + FILTER
# ==========================
class AttendanceListView(generics.ListAPIView):
    """
    GET /api/attend/list?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
                         &department_id=&employee_id=&worksite_id=
                         &status=&type=
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = AttendanceSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Attendance.objects.select_related("employee","employee__department","worksite").order_by("-ts")
        p = self.request.query_params

        df = p.get("date_from"); dt = p.get("date_to")
        if df: qs = qs.filter(local_date__gte=df)
        if dt: qs = qs.filter(local_date__lte=dt)

        if p.get("department_id"): qs = qs.filter(employee__department_id=p["department_id"])
        if p.get("employee_id"):   qs = qs.filter(employee_id=p["employee_id"])
        if p.get("worksite_id"):   qs = qs.filter(worksite_id=p["worksite_id"])
        if p.get("status"):        qs = qs.filter(status=p["status"])
        if p.get("type"):          qs = qs.filter(type=p["type"])
        return qs


# ==========================
# 3) EXPORT CSV NHANH
# ==========================
class AttendanceExportCSVView(APIView):
    """GET /api/attend/export (nhận các query y như /list)"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # tái dùng filter như list:
        list_view = AttendanceListView()
        list_view.request = request
        qs = list_view.get_queryset()

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="attendance.csv"'
        w = csv.writer(resp)
        w.writerow([
            "id","local_date","ts","employee_no","full_name","department",
            "type","status","worksite","distance_m","lat","lng","accuracy","source","ip","note"
        ])
        for a in qs:
            w.writerow([
                a.id, a.local_date, a.ts.isoformat(),
                a.employee.userID, a.employee.full_name, a.employee.department.name,
                a.type, a.status,
                (a.worksite.code if a.worksite else ""), a.distance_m,
                a.lat, a.lng, a.accuracy, a.source, a.ip, a.note
            ])
        return resp


# # ==========================
# # 4) DANH MỤC CHO UI FILTER
# # ==========================
# class DepartmentListView(generics.ListAPIView):
#     permission_classes = [permissions.AllowAny]
#     serializer_class = DepartmentSerializer
#     queryset = Department.objects.filter(is_active=True).order_by("name")

# class EmployeeListView(generics.ListAPIView):
#     permission_classes = [permissions.AllowAny]
#     serializer_class = EmployeeSerializer
#     queryset = Employee.objects.filter(is_active=True).select_related("department").order_by("full_name")

# class WorksiteListView(generics.ListAPIView):
#     permission_classes = [permissions.AllowAny]
#     serializer_class = WorksiteSerializer
#     queryset = Worksite.objects.filter(active=True).order_by("name")



class EmployeeListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/employees      -> danh sách nhân viên (đang active)
    POST /api/employees      -> tạo nhân viên mới
    """
    permission_classes = [permissions.AllowAny]   # đổi theo nhu cầu auth của bạn
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related("department").order_by("full_name")
    pagination_class = None  # <<< tắt phân trang

class EmployeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/employees/<id>
    PUT    /api/employees/<id>
    PATCH  /api/employees/<id>
    DELETE /api/employees/<id>
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related("department")

class DepartmentListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/departments      -> danh sách phòng ban (đang active)
    POST /api/departments      -> tạo phòng ban mới
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.filter(is_active=True).order_by("name")

class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/departments/<id>
    PUT    /api/departments/<id>
    PATCH  /api/departments/<id>
    DELETE /api/departments/<id>
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()    

class WorksiteListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/worksites      -> danh sách công trường (đang active)
    POST /api/worksites      -> tạo công trường mới
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = WorksiteSerializer
    queryset = Worksite.objects.filter(active=True).order_by("name")
class WorksiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/worksites/<id>
    PUT    /api/worksites/<id>
    PATCH  /api/worksites/<id>
    DELETE /api/worksites/<id>
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = WorksiteSerializer
    queryset = Worksite.objects.all()

class EmployeeWorksiteListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmployeeWorksiteSerializer
    queryset = EmployeeWorksite.objects.select_related("employee","worksite").order_by("employee__full_name")
    parser_classes = [JSONParser]  # ép nhận JSON cho chắc

    def create(self, request, *args, **kwargs):
        print("CT =", request.content_type)
        print("DATA =", request.data)
        s = self.get_serializer(data=request.data)
        print("FIELDS =", list(s.fields.keys()))
        if not s.is_valid():
            print("ERRORS =", s.errors)
            # trả về cả debug để thấy rõ
            return Response({"debug": {"data": request.data, "fields": list(s.fields.keys())}, "errors": s.errors}, status=400)
        return super().create(request, *args, **kwargs)
class EmployeeWorksiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/empworksites/<id>
    PUT    /api/empworksites/<id>
    PATCH  /api/empworksites/<id>
    DELETE /api/empworksites/<id>
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = EmployeeWorksiteSerializer
    queryset = EmployeeWorksite.objects.select_related("employee","worksite")

