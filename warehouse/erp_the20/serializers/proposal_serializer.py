from rest_framework import serializers
from erp_the20.models import Proposal

class ProposalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proposal
        fields = [
            "id","employee_id","manager_id","type","title","content",
            "status","decision_note","created_at","updated_at"
        ]
        read_only_fields = ["status","created_at","updated_at"]
