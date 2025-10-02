# ============================================
# jira/selectors/comment.py
# ============================================
from typing import List, Optional
from django.db.models import QuerySet
from jira.models import Comment
from jira.clients.user_client import UserServiceClient


class CommentSelector:
    
    @staticmethod
    def get_comment_by_id(comment_id: int) -> Optional[Comment]:
        """Get single comment"""
        try:
            return Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            return None
    
    @staticmethod
    def get_comments_by_issue(issue_id: int) -> QuerySet:
        """Get all comments for an issue"""
        return Comment.objects.filter(issue_id=issue_id).order_by('created_at')
    
    @staticmethod
    def enrich_comments_with_users(comments: List[Comment]) -> List[Comment]:
        """Fetch and attach user data to comments"""
        author_ids = list(set([str(c.author_id) for c in comments]))
        users_dict = UserServiceClient.get_users_by_ids(author_ids)
        
        for comment in comments:
            comment.author_data = users_dict.get(str(comment.author_id))
        
        return comments