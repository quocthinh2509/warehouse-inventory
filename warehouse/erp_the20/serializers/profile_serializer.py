from rest_framework import serializers
from erp_the20.models import EmployeeProfile

class EmployeeProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeProfile
        fields = [
            "user_id","full_name","cccd","date_of_birth","address","first_day_in_job",
            "email","doc_link","picture_link","offer_content","salary","degree","old_company",
            "tax_code","bhxh","car","temporary_address","phone","emergency_contact","emergency_phone",
            "note","created_at","updated_at"
        ]
        read_only_fields = ["created_at","updated_at"]
