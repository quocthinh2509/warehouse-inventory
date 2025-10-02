# ============================================
# jira/serializers/comment.py
# ============================================
from rest_framework import serializers
from jira.models import Comment


class CommentCreateSerializer(serializers.Serializer):
    content = serializers.CharField()


class CommentUpdateSerializer(serializers.Serializer):
    content = serializers.CharField()


class CommentOutputSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = ['id', 'author', 'content', 'created_at', 'updated_at']
    
    def get_author(self, obj):
        return getattr(obj, 'author_data', None)