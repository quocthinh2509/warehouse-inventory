from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from erp_the20.models import ShiftTemplate

class ShiftTemplateReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = [
            "id", "code", "name", "start_time", "end_time",
            "break_minutes", "overnight", "pay_factor",
            "created_at", "updated_at", "deleted_at",
        ]

class ShiftTemplateWriteSerializer(serializers.ModelSerializer):
    # Unique chỉ kiểm tra trên bản active (deleted_at IS NULL)
    code = serializers.CharField(
        max_length=16,
        validators=[UniqueValidator(
            queryset=ShiftTemplate.objects.filter(deleted_at__isnull=True),
            message="Code đã tồn tại ở bản active."
        )]
    )

    class Meta:
        model = ShiftTemplate
        fields = [
            "code", "name", "start_time", "end_time",
            "break_minutes", "overnight", "pay_factor",
        ]

    def validate_break_minutes(self, v: int):
        if v < 0:
            raise serializers.ValidationError("break_minutes phải ≥ 0.")
        if v > 480:
            raise serializers.ValidationError("break_minutes quá lớn (≤ 480).")
        return v

    def validate(self, attrs):
        inst = getattr(self, "instance", None)
        start = attrs.get("start_time", getattr(inst, "start_time", None))
        end = attrs.get("end_time", getattr(inst, "end_time", None))
        overnight = attrs.get("overnight", getattr(inst, "overnight", False))

        if start and end and not overnight and end <= start:
            raise serializers.ValidationError(
                {"end_time": "Ca không qua đêm (overnight=False) thì end_time phải > start_time."}
            )
        return attrs
