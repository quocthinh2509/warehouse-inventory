# ============================================
# jira/services/comment.py
# ============================================
from django.core.exceptions import PermissionDenied, ValidationError
from jira.models import Comment, Issue
from jira.services.issue import IssueService


class CommentService:
    
    @staticmethod
    def create_comment(
        *,
        issue: Issue,
        author_id: str,
        content: str
    ) -> Comment:
        """Create a comment on an issue"""
        
        # Check membership
        IssueService._check_project_membership(issue.project, author_id)
        
        comment = Comment.objects.create(
            issue=issue,
            author_id=author_id,
            content=content
        )
        
        return comment
    
    @staticmethod
    def update_comment(
        *,
        comment: Comment,
        user_id: str,
        content: str
    ) -> Comment:
        """Update a comment"""
        
        # Only author can update
        if str(comment.author_id) != user_id:
            raise PermissionDenied("Only comment author can update comment")
        
        comment.content = content
        comment.save()
        
        return comment
    
    @staticmethod
    def delete_comment(*, comment: Comment, user_id: str) -> None:
        """Delete a comment"""
        
        # Author or project owner can delete
        if str(comment.author_id) != user_id and str(comment.issue.project.owner_id) != user_id:
            raise PermissionDenied("Only comment author or project owner can delete comment")
        
        comment.delete()
