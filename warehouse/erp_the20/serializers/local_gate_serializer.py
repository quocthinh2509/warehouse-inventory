# erp_the20/serializers/local_gate_serializer.py
from rest_framework import serializers

class AttestationSerializer(serializers.Serializer):
    agent_code = serializers.CharField()
    client_ip = serializers.CharField(required=False, allow_blank=True)
    purpose = serializers.CharField()
    nonce = serializers.CharField(required=False, allow_blank=True)
    iat = serializers.IntegerField()
    exp = serializers.IntegerField()

class AttestationProofSerializer(serializers.Serializer):
    attestation = AttestationSerializer()
    sig = serializers.CharField()
