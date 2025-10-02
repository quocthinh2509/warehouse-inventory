# ============================================
# jira/views/comment.py
# ============================================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from jira.serializers.comment import (
    CommentCreateSerializer,
    CommentUpdateSerializer,
    CommentOutputSerializer
)
from jira.selectors.comment import CommentSelector
from jira.selectors.issue import IssueSelector
from jira.services.comment import CommentService


class CommentListCreateAPIView(APIView):
    """
    GET: List comments for an issue
    POST: Create a comment
    
    Path params:
    - issue_id: int
    
    Request body (POST):
    - content: string (required)
    """
    
    def get(self, request, issue_id):
        comments = CommentSelector.get_comments_by_issue(issue_id)
        comments_list = list(comments)
        
        # Enrich with user data
        comments_with_users = CommentSelector.enrich_comments_with_users(comments_list)
        
        serializer = CommentOutputSerializer(comments_with_users, many=True)
        return Response(serializer.data)
    
    def post(self, request, issue_id):
        issue = IssueSelector.get_issue_by_id(issue_id)
        
        if not issue:
            return Response(
                {'error': 'Issue not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        comment = CommentService.create_comment(
            issue=issue,
            author_id=str(request.user.id),
            **serializer.validated_data
        )
        
        # Enrich and return
        comments_with_users = CommentSelector.enrich_comments_with_users([comment])
        output_serializer = CommentOutputSerializer(comments_with_users[0])
        
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class CommentDetailAPIView(APIView):
    """
    PUT: Update comment
    DELETE: Delete comment
    
    Path params:
    - comment_id: int
    """
    
    def put(self, request, comment_id):
        comment = CommentSelector.get_comment_by_id(comment_id)
        
        if not comment:
            return Response(
                {'error': 'Comment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CommentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        updated_comment = CommentService.update_comment(
            comment=comment,
            user_id=str(request.user.id),
            **serializer.validated_data
        )
        
        comments_with_users = CommentSelector.enrich_comments_with_users([updated_comment])
        output_serializer = CommentOutputSerializer(comments_with_users[0])
        
        return Response(output_serializer.data)
    
    def delete(self, request, comment_id):
        comment = CommentSelector.get_comment_by_id(comment_id)
        
        if not comment:
            return Response(
                {'error': 'Comment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        CommentService.delete_comment(
            comment=comment,
            user_id=str(request.user.id)
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
