# ============================================
# jira/serializers/issue.py
# ============================================
from rest_framework import serializers
from jira.models import Issue


class IssueCreateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    issue_type = serializers.ChoiceField(choices=Issue.IssueType.choices)
    priority = serializers.ChoiceField(
        choices=Issue.Priority.choices,
        default=Issue.Priority.MEDIUM
    )
    status_id = serializers.IntegerField()
    assignee_id = serializers.UUIDField(required=False, allow_null=True)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    sprint_id = serializers.IntegerField(required=False, allow_null=True)
    estimate = serializers.IntegerField(required=False, allow_null=True)


class IssueUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=Issue.Priority.choices,
        required=False
    )
    status_id = serializers.IntegerField(required=False)
    assignee_id = serializers.UUIDField(required=False, allow_null=True)
    sprint_id = serializers.IntegerField(required=False, allow_null=True)
    estimate = serializers.IntegerField(required=False, allow_null=True)


class IssueOutputSerializer(serializers.ModelSerializer):
    assignee = serializers.SerializerMethodField()
    reporter = serializers.SerializerMethodField()
    status_name = serializers.CharField(source='status.name', read_only=True)
    sprint_name = serializers.CharField(source='sprint.name', read_only=True)
    
    class Meta:
        model = Issue
        fields = [
            'id', 'key', 'title', 'description', 'issue_type',
            'priority', 'status_name', 'assignee', 'reporter',
            'sprint_name', 'estimate', 'created_at', 'updated_at'
        ]
    
    def get_assignee(self, obj):
        return getattr(obj, 'assignee_data', None)
    
    def get_reporter(self, obj):
        return getattr(obj, 'reporter_data', None)


class IssueListOutputSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views"""
    assignee = serializers.SerializerMethodField()
    reporter = serializers.SerializerMethodField()
    status_name = serializers.CharField(source='status.name', read_only=True)
    
    class Meta:
        model = Issue
        fields = [
            'id', 'key', 'title', 'issue_type', 'priority',
            'status_name', 'assignee', 'reporter', 'created_at'
        ]
    
    def get_assignee(self, obj):
        assignee_data = getattr(obj, 'assignee_data', None)
        if assignee_data:
            return {'id': assignee_data['id'], 'name': assignee_data.get('name')}
        return None
    
    def get_reporter(self, obj):
        reporter_data = getattr(obj, 'reporter_data', None)
        if reporter_data:
            return {'id': reporter_data['id'], 'name': reporter_data.get('name')}
        return None