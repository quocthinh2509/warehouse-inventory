# ============================================
# jira/serializers/project.py
# ============================================
from rest_framework import serializers
from jira.models import Project


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    key = serializers.CharField(max_length=10)
    description = serializers.CharField(required=False, allow_blank=True)
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )


class ProjectUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )


class ProjectOutputSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'key', 'description',
            'owner', 'members', 'created_at', 'updated_at'
        ]
    
    def get_owner(self, obj):
        return getattr(obj, 'owner_data', None)
    
    def get_members(self, obj):
        return getattr(obj, 'members_data', [])