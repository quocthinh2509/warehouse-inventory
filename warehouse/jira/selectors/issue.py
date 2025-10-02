# ============================================
# jira/selectors/issue.py
# ============================================
from typing import List, Optional
from django.db.models import QuerySet, Q
from jira.models import Issue
from jira.clients.user_client import UserServiceClient


class IssueSelector:
    
    @staticmethod
    def get_issue_by_id(issue_id: int) -> Optional[Issue]:
        """Get single issue with related data"""
        try:
            return Issue.objects.select_related(
                'project', 'status', 'sprint', 'parent'
            ).get(id=issue_id)
        except Issue.DoesNotExist:
            return None
    
    @staticmethod
    def get_issue_by_key(key: str) -> Optional[Issue]:
        """Get issue by key"""
        try:
            return Issue.objects.select_related(
                'project', 'status', 'sprint'
            ).get(key=key)
        except Issue.DoesNotExist:
            return None
    
    @staticmethod
    def get_issues_list(
        project_id: int = None,
        status_id: int = None,
        assignee_id: str = None,
        reporter_id: str = None,
        sprint_id: int = None,
        issue_type: str = None,
        search: str = None
    ) -> QuerySet:
        """Get filtered issues list with optimization"""
        queryset = Issue.objects.select_related(
            'project', 'status', 'sprint'
        )
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        if status_id:
            queryset = queryset.filter(status_id=status_id)
        
        if assignee_id:
            queryset = queryset.filter(assignee_id=assignee_id)
        
        if reporter_id:
            queryset = queryset.filter(reporter_id=reporter_id)
        
        if sprint_id:
            queryset = queryset.filter(sprint_id=sprint_id)
        
        if issue_type:
            queryset = queryset.filter(issue_type=issue_type)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(key__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def enrich_issues_with_users(issues: List[Issue]) -> List[Issue]:
        """Fetch and attach user data to issues"""
        user_ids = set()
        
        for issue in issues:
            if issue.assignee_id:
                user_ids.add(str(issue.assignee_id))
            user_ids.add(str(issue.reporter_id))
        
        users_dict = UserServiceClient.get_users_by_ids(list(user_ids))
        
        for issue in issues:
            issue.assignee_data = users_dict.get(str(issue.assignee_id)) if issue.assignee_id else None
            issue.reporter_data = users_dict.get(str(issue.reporter_id))
        
        return issues