# ============================================
# jira/views/issue.py
# ============================================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from jira.serializers.issue import (
    IssueCreateSerializer,
    IssueUpdateSerializer,
    IssueOutputSerializer,
    IssueListOutputSerializer
)
from jira.selectors.issue import IssueSelector
from jira.services.issue import IssueService


class IssuePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class IssueListCreateAPIView(APIView):
    """
    GET: List issues with filters
    POST: Create a new issue
    
    Query params (GET):
    - project_id: int (optional)
    - status_id: int (optional)
    - assignee_id: UUID (optional)
    - reporter_id: UUID (optional)
    - sprint_id: int (optional)
    - issue_type: string (optional)
    - search: string (optional)
    - page: int
    - page_size: int
    
    Request body (POST):
    - project_id: int (required)
    - title: string (required)
    - description: string (optional)
    - issue_type: string (required: TASK/BUG/STORY/EPIC)
    - priority: string (optional)
    - status_id: int (required)
    - assignee_id: UUID (optional)
    - parent_id: int (optional)
    - sprint_id: int (optional)
    - estimate: int (optional)
    """
    
    def get(self, request):
        filters = {
            'project_id': request.query_params.get('project_id'),
            'status_id': request.query_params.get('status_id'),
            'assignee_id': request.query_params.get('assignee_id'),
            'reporter_id': request.query_params.get('reporter_id'),
            'sprint_id': request.query_params.get('sprint_id'),
            'issue_type': request.query_params.get('issue_type'),
            'search': request.query_params.get('search'),
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        issues = IssueSelector.get_issues_list(**filters)
        
        # Paginate
        paginator = IssuePagination()
        page = paginator.paginate_queryset(issues, request)
        
        # Enrich with user data
        issues_with_users = IssueSelector.enrich_issues_with_users(page)
        
        serializer = IssueListOutputSerializer(issues_with_users, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    def post(self, request):
        serializer = IssueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        issue = IssueService.create_issue(
            reporter_id=str(request.user.id),
            **serializer.validated_data
        )
        
        # Enrich and return
        issues_with_users = IssueSelector.enrich_issues_with_users([issue])
        output_serializer = IssueOutputSerializer(issues_with_users[0])
        
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class IssueDetailAPIView(APIView):
    """
    GET: Retrieve issue details
    PUT: Update issue
    DELETE: Delete issue
    
    Path params:
    - issue_id: int
    """
    
    def get(self, request, issue_id):
        issue = IssueSelector.get_issue_by_id(issue_id)
        
        if not issue:
            return Response(
                {'error': 'Issue not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        issues_with_users = IssueSelector.enrich_issues_with_users([issue])
        serializer = IssueOutputSerializer(issues_with_users[0])
        
        return Response(serializer.data)
    
    def put(self, request, issue_id):
        issue = IssueSelector.get_issue_by_id(issue_id)
        
        if not issue:
            return Response(
                {'error': 'Issue not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = IssueUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        updated_issue = IssueService.update_issue(
            issue=issue,
            user_id=str(request.user.id),
            **serializer.validated_data
        )
        
        issues_with_users = IssueSelector.enrich_issues_with_users([updated_issue])
        output_serializer = IssueOutputSerializer(issues_with_users[0])
        
        return Response(output_serializer.data)
    
    def delete(self, request, issue_id):
        issue = IssueSelector.get_issue_by_id(issue_id)
        
        if not issue:
            return Response(
                {'error': 'Issue not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        IssueService.delete_issue(
            issue=issue,
            user_id=str(request.user.id)
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)