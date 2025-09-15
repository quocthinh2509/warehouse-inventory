from rest_framework import serializers
from .models import CheckEvent

class CheckEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckEvent
        fields = ["id","type","ts","lat","lng","accuracy","ua","ip","note"]
        read_only_fields = ["id","ts","ua","ip"]
