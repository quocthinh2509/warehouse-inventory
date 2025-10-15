from rest_framework import serializers
from erp_the20.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id","title","channel","object_type","object_id",
            "to_user","recipients","payload",
            "delivered","delivered_at","attempt_count","last_error",
            "created_at","updated_at"
        ]
        read_only_fields = fields
