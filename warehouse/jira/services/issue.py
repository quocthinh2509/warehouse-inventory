# ============================================
# jira/services/issue.py
# ============================================
from typing import Dict, Optional
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from jira.models import Issue, Project, Status, IssueHistory
from jira.clients.user_client import UserServiceClient


class IssueService:
    
    @staticmethod
    def _check_project_membership(project: Project, user_id: str) -> None:
        """Verify user is a member of the project"""
        if user_id not in project.member_ids:
            raise PermissionDenied("User is not a member of this project")
    
    @staticmethod
    def _generate_issue_key(project: Project) -> str:
        """Generate next issue key for project"""
        last_issue = Issue.objects.filter(project=project).order_by('-id').first()
        number = (last_issue.id + 1) if last_issue else 1
        return f"{project.key}-{number}"
    
    @staticmethod
    def _log_history(issue: Issue, user_id: str, field_name: str, old_value: str, new_value: str) -> None:
        """Log issue change to history"""
        IssueHistory.objects.create(
            issue=issue,
            user_id=user_id,
            field_name=field_name,
            old_value=str(old_value) if old_value else '',
            new_value=str(new_value) if new_value else ''
        )
    
    @staticmethod
    @transaction.atomic
    def create_issue(
        *,
        project_id: int,
        title: str,
        issue_type: str,
        status_id: int,
        reporter_id: str,
        description: str = '',
        priority: str = Issue.Priority.MEDIUM,
        assignee_id: Optional[str] = None,
        parent_id: Optional[int] = None,
        sprint_id: Optional[int] = None,
        estimate: Optional[int] = None
    ) -> Issue:
        """Create a new issue"""
        
        # Get and validate project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError("Project does not exist")
        
        # Check membership
        IssueService._check_project_membership(project, reporter_id)
        
        # Validate status belongs to project
        try:
            status = Status.objects.get(id=status_id, project=project)
        except Status.DoesNotExist:
            raise ValidationError("Status does not belong to this project")
        
        # Validate assignee if provided
        if assignee_id:
            IssueService._check_project_membership(project, assignee_id)
        
        # Generate key
        key = IssueService._generate_issue_key(project)
        
        # Create issue
        issue = Issue.objects.create(
            project=project,
            key=key,
            title=title,
            description=description,
            issue_type=issue_type,
            priority=priority,
            status=status,
            assignee_id=assignee_id,
            reporter_id=reporter_id,
            parent_id=parent_id,
            sprint_id=sprint_id,
            estimate=estimate
        )
        
        # Log creation
        IssueService._log_history(
            issue=issue,
            user_id=reporter_id,
            field_name='created',
            old_value='',
            new_value=f'Issue created'
        )
        
        return issue
    
    @staticmethod
    @transaction.atomic
    def update_issue(
        *,
        issue: Issue,
        user_id: str,
        **data
    ) -> Issue:
        """Update issue and log changes"""
        
        # Check membership
        IssueService._check_project_membership(issue.project, user_id)
        
        # Track changes for history
        changes = {}
        
        # Handle status change
        if 'status_id' in data:
            new_status = Status.objects.get(id=data['status_id'], project=issue.project)
            if issue.status != new_status:
                changes['status'] = (issue.status.name, new_status.name)
                issue.status = new_status
        
        # Handle other fields
        field_mapping = {
            'title': 'title',
            'description': 'description',
            'priority': 'priority',
            'assignee_id': 'assignee_id',
            'sprint_id': 'sprint_id',
            'estimate': 'estimate'
        }
        
        for field, attr in field_mapping.items():
            if field in data:
                old_value = getattr(issue, attr)
                new_value = data[field]
                if old_value != new_value:
                    changes[field] = (old_value, new_value)
                    setattr(issue, attr, new_value)
        
        issue.save()
        
        # Log all changes
        for field_name, (old_val, new_val) in changes.items():
            IssueService._log_history(
                issue=issue,
                user_id=user_id,
                field_name=field_name,
                old_value=old_val,
                new_value=new_val
            )
        
        return issue
    
    @staticmethod
    def delete_issue(*, issue: Issue, user_id: str) -> None:
        """Delete issue"""
        
        # Only reporter or project owner can delete
        if str(issue.reporter_id) != user_id and str(issue.project.owner_id) != user_id:
            raise PermissionDenied("Only reporter or project owner can delete issue")
        
        issue.delete()
