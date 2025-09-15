# models.py
from django.db import models
from django.db.models import Q
from django.utils import timezone

class Department(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)            # unique=False để linh hoạt
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return f"{self.code} - {self.name}"

class Employee(models.Model):
    userID = models.CharField(max_length=20, unique=True)  # was: userID
    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)  # PROTECT
    position = models.CharField(max_length=300, blank=True)
    lark_user_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)                # NEW
    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["userID","full_name","department"])]
    def __str__(self): return f"{self.userID} - {self.full_name} - {self.department.name}"

class Worksite(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    lat = models.FloatField()
    lng = models.FloatField()
    radius_m = models.PositiveIntegerField(default=200)
    active = models.BooleanField(default=True)                     # NEW
    description = models.TextField(blank=True)
    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["code","name"])]
        constraints = [                                           # NEW: toạ độ hợp lệ
            models.CheckConstraint(check=Q(lat__gte=-90) & Q(lat__lte=90), name="ck_ws_lat_range"),
            models.CheckConstraint(check=Q(lng__gte=-180) & Q(lng__lte=180), name="ck_ws_lng_range"),
            models.CheckConstraint(check=Q(radius_m__gt=0), name="ck_ws_radius_pos"),
        ]
    def __str__(self): return f"{self.code} - {self.name}"

class EmployeeWorksite(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    worksite = models.ForeignKey(Worksite, on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False)
    class Meta:
        unique_together = [("employee","worksite")]
        indexes = [models.Index(fields=["employee","worksite"])]
        # PostgreSQL/SQLite (partial index) hỗ trợ:
        constraints = [
            models.UniqueConstraint(
                fields=["employee"], condition=Q(is_default=True),
                name="uniq_one_default_site_per_employee"
            )
        ]
    def __str__(self): return f"{self.employee} @ {self.worksite}"

class Attendance(models.Model):
    TYPE = (("IN","IN"), ("OUT","OUT"))
    STATUS = (("accepted","accepted"),("out_of_geofence","out_of_geofence"),
              ("low_accuracy","low_accuracy"),("duplicate","duplicate"),
              ("blocked","blocked"),("manual","manual"))
    SOURCE = (("web","web"),("lark","lark"),("pwa","pwa"),("api","api"),("admin","admin"))

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="attendances")
    worksite = models.ForeignKey(Worksite, on_delete=models.PROTECT, null=True, blank=True)
    type = models.CharField(max_length=3, choices=TYPE)
    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    local_date = models.DateField(db_index=True, default=timezone.localdate)  # NEW default

    # Toạ độ chấm công 
    lat = models.FloatField() # CHECK: -90 <= lat <= 90
    lng = models.FloatField() # CHECK: -180 <= lng <= 180
    accuracy = models.FloatField(null=True, blank=True) # độ sai số ước lượng ( trình duyệt trả về , càng nhỏ càng tốt)
    distance_m = models.IntegerField(null=True, blank=True) # khoản cách đến worksite

    status = models.CharField(max_length=20, choices=STATUS, default="accepted", db_index=True)
    note = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=10, choices=SOURCE, default="web")
    ip = models.GenericIPAddressField(null=True, blank=True)
    ua = models.TextField(blank=True)

    class Meta:
        ordering = ["-ts"]
        indexes = [
            models.Index(fields=["employee","local_date"]),
            models.Index(fields=["worksite","ts"]),
            models.Index(fields=["status"]),
        ]
        constraints = [                                          # NEW: kiểm dữ liệu
            models.CheckConstraint(check=Q(lat__gte=-90) & Q(lat__lte=90), name="ck_att_lat_range"),
            models.CheckConstraint(check=Q(lng__gte=-180) & Q(lng__lte=180), name="ck_att_lng_range"),
            models.CheckConstraint(check=Q(accuracy__gte=0) | Q(accuracy__isnull=True), name="ck_att_acc_nonneg"),
            models.CheckConstraint(check=Q(distance_m__gte=0) | Q(distance_m__isnull=True), name="ck_att_dist_nonneg"),
        ]

    def __str__(self):
        return f"{self.employee} {self.type} {self.ts:%Y-%m-%d %H:%M:%S} ({self.status})"
