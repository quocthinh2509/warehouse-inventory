
# ─────────────────────────────────────────────────────────────
# erp/serializers/attendance.py
# ─────────────────────────────────────────────────────────────
from rest_framework import serializers
from erp.models import Employee, Worksite, Shift, AttendanceRecord
from erp.services.attendance_validators import validate_new_check, validate_geo
from django.utils import timezone

class AttendanceCreateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    worksite_id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=['in','out'])
    when = serializers.DateTimeField(required=False)
    shift_id = serializers.IntegerField(required=False)
    lat = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    accuracy_m = serializers.IntegerField(required=False)
    method = serializers.ChoiceField(choices=['web','mobile','lark','api'], default='web')
    note_user = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated):
        emp = Employee.objects.get(pk=validated['employee_id'])
        ws = Worksite.objects.get(pk=validated['worksite_id'])
        when = validated.get('when') or timezone.now()
        kind = validated['kind']
        lat, lng = validated.get('lat'), validated.get('lng')
        accuracy_m = validated.get('accuracy_m')

        ok, reason = validate_new_check(emp, when, kind)
        if not ok:
            raise serializers.ValidationError({'detail':'Duplicate within time window','code':reason})
        ok, reason = validate_geo(ws, lat, lng, accuracy_m)
        if not ok:
            raise serializers.ValidationError({'detail':'Location invalid','code':reason})

        if kind == 'in':
            rec = AttendanceRecord.objects.create(
                employee=emp, worksite=ws, shift_id=validated.get('shift_id'),
                check_in_at=when, check_in_lat=lat, check_in_lng=lng,
                accuracy_m=accuracy_m, method=validated.get('method','web'),
                note_user=validated.get('note_user','')
            )
        else:
            rec = AttendanceRecord.objects.filter(employee=emp, worksite=ws, check_out_at__isnull=True).order_by('-check_in_at').first()
            if not rec:
                raise serializers.ValidationError({'detail':'No open check-in to close','code':'missing_open_in'})
            rec.check_out_at = when
            rec.check_out_lat = lat
            rec.check_out_lng = lng
            if validated.get('note_user'):
                rec.note_user = validated['note_user']
            rec.save()
        return rec

class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    worksite_name = serializers.CharField(source='worksite.name', read_only=True)
    class Meta:
        model = AttendanceRecord
        fields = ['id','employee','employee_name','worksite','worksite_name','shift','check_in_at','check_out_at',
                  'check_in_lat','check_in_lng','check_out_lat','check_out_lng','method','accuracy_m','note_user','is_valid','invalid_reason','created_at']
