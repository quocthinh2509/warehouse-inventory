# serializers.py
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from .models import (
    Department, Employee, Worksite, EmployeeWorksite, Attendance
)

# ------------ Department ------------
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name", "description", "is_active"]


# ------------ Employee ------------
class EmployeeSerializer(serializers.ModelSerializer):
    # Read nested
    department = DepartmentSerializer(read_only=True)
    # Write by id
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source="department", write_only=True
    )

    class Meta:
        model = Employee
        fields = [
            "id", "userID", "full_name", "email", "phone",
            "position", "lark_user_id", "is_active",
            "department", "department_id",
        ]


# ------------ Worksite ------------
class WorksiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worksite
        fields = [
            "id", "code", "name", "address",
            "lat", "lng", "radius_m",
            "active", "description",
        ]

    # Bắt lỗi sớm ở tầng API (ngoài CheckConstraint ở DB)
    def validate(self, attrs):
        lat = attrs.get("lat", getattr(self.instance, "lat", None))
        lng = attrs.get("lng", getattr(self.instance, "lng", None))
        radius = attrs.get("radius_m", getattr(self.instance, "radius_m", None))

        if lat is not None and not (-90 <= lat <= 90):
            raise serializers.ValidationError({"lat": "lat phải nằm trong [-90, 90]."})
        if lng is not None and not (-180 <= lng <= 180):
            raise serializers.ValidationError({"lng": "lng phải nằm trong [-180, 180]."})
        if radius is not None and radius <= 0:
            raise serializers.ValidationError({"radius_m": "radius_m phải > 0."})
        return attrs


class EmployeeWorksiteSerializer(serializers.ModelSerializer):
    # Read nested
    employee = serializers.SerializerMethodField(read_only=True)
    worksite = serializers.SerializerMethodField(read_only=True)

    # Write by id
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source="employee", write_only=True
    )
    worksite_id = serializers.PrimaryKeyRelatedField(
        queryset=Worksite.objects.all(), source="worksite", write_only=True
    )

    class Meta:
        model = EmployeeWorksite
        fields = ["id", "employee", "employee_id", "worksite", "worksite_id", "is_default"]
        extra_kwargs = {
            "employee": {"read_only": True, "required": False},
            "worksite": {"read_only": True, "required": False},
        }
        # ⚠️ GỠ UniqueTogetherValidator để tránh lỗi "required"
        validators = []  # dùng validate() tự viết + ràng buộc ở model

    def validate(self, attrs):
        emp = attrs.get("employee") or getattr(self.instance, "employee", None)
        ws  = attrs.get("worksite") or getattr(self.instance, "worksite", None)
        if not emp:
            raise serializers.ValidationError({"employee_id": "This field is required."})
        if not ws:
            raise serializers.ValidationError({"worksite_id": "This field is required."})

        # check trùng cặp (employee, worksite) khi create/update
        qs = EmployeeWorksite.objects.filter(employee=emp, worksite=ws)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"non_field_errors": ["Cặp (employee, worksite) đã tồn tại."]})
        return attrs

    def get_employee(self, obj):
        return {"id": obj.employee.id, "userID": obj.employee.userID, "full_name": obj.employee.full_name}

    def get_worksite(self, obj):
        return {"id": obj.worksite.id, "code": obj.worksite.code, "name": obj.worksite.name}


# ------------ Attendance ------------
# Gọn nested để trả ra dashboard (không quá nặng)
class _EmployeeBriefSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "userID", "full_name", "department_name"]


class _WorksiteBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worksite
        fields = ["id", "code", "name"]


class AttendanceSerializer(serializers.ModelSerializer):
    # Read nested
    employee = _EmployeeBriefSerializer(read_only=True)
    worksite  = _WorksiteBriefSerializer(read_only=True)

    # Write by id
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source="employee", write_only=True, required=True
    )
    worksite_id = serializers.PrimaryKeyRelatedField(
        queryset=Worksite.objects.all(), source="worksite", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Attendance
        fields = [
            "id",
            # who/where
            "employee", "employee_id",
            "worksite", "worksite_id",
            # event
            "type", "ts", "local_date",
            # location
            "lat", "lng", "accuracy", "distance_m",
            # status & meta
            "status", "note", "source", "ip", "ua",
        ]
        read_only_fields = [
            # hệ thống tự set
            "id", "ts", "local_date",
            # thường tính ở view/service (geofence + rules)
            "status", "distance_m", "ip", "ua",
            # và cả worksite nếu bạn quyết định match tự động
            # "worksite", "worksite_id",
        ]

    # Validate biên độ lat/lng & accuracy cho request tạo/sửa
    def validate(self, attrs):
        # Khi update partial, lấy giá trị từ instance nếu không gửi lên
        lat = attrs.get("lat", getattr(self.instance, "lat", None))
        lng = attrs.get("lng", getattr(self.instance, "lng", None))
        acc = attrs.get("accuracy", getattr(self.instance, "accuracy", None))

        if lat is None or lng is None:
            raise serializers.ValidationError("Cần cung cấp lat và lng.")

        if not (-90 <= lat <= 90):
            raise serializers.ValidationError({"lat": "lat phải nằm trong [-90, 90]."})
        if not (-180 <= lng <= 180):
            raise serializers.ValidationError({"lng": "lng phải nằm trong [-180, 180]."})

        if acc is not None and acc < 0:
            raise serializers.ValidationError({"accuracy": "accuracy phải >= 0."})
        return attrs
