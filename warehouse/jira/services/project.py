# ============================================
# jira/services/project.py
# ============================================
from typing import Dict, List
from django.core.exceptions import PermissionDenied, ValidationError
from jira.models import Project, Status
from jira.clients.user_client import UserServiceClient


class ProjectService:
    
    @staticmethod
    def create_project(
        *,
        name: str,
        key: str,
        owner_id: str,
        description: str = '',
        member_ids: List[str] = None
    ) -> Project:
        """Create a new project"""
        
        # Validate key is unique
        if Project.objects.filter(key=key).exists():
            raise ValidationError(f"Project key '{key}' already exists")
        
        # Verify owner exists
        if not UserServiceClient.verify_user_exists(owner_id):
            raise ValidationError("Owner user does not exist")
        
        # Create project
        member_ids = member_ids or []
        if owner_id not in member_ids:
            member_ids.append(owner_id)
        
        project = Project.objects.create(
            name=name,
            key=key,
            description=description,
            owner_id=owner_id,
            member_ids=member_ids
        )
        
        # Create default statuses
        default_statuses = [
            ('To Do', 0, False),
            ('In Progress', 1, False),
            ('Done', 2, True),
        ]
        
        for status_name, order, is_done in default_statuses:
            Status.objects.create(
                name=status_name,
                project=project,
                order=order,
                is_done=is_done
            )
        
        return project
    
    @staticmethod
    def update_project(
        *,
        project: Project,
        user_id: str,
        **data
    ) -> Project:
        """Update project"""
        
        # Check permission
        if str(project.owner_id) != user_id:
            raise PermissionDenied("Only project owner can update project")
        
        # Update fields
        for field, value in data.items():
            if hasattr(project, field):
                setattr(project, field, value)
        
        project.save()
        return project
    
    @staticmethod
    def delete_project(*, project: Project, user_id: str) -> None:
        """Delete project"""
        
        if str(project.owner_id) != user_id:
            raise PermissionDenied("Only project owner can delete project")
        
        project.delete()
    
    @staticmethod
    def add_member(*, project: Project, user_id: str, member_id: str) -> Project:
        """Add member to project"""
        
        if str(project.owner_id) != user_id:
            raise PermissionDenied("Only project owner can add members")
        
        if not UserServiceClient.verify_user_exists(member_id):
            raise ValidationError("User does not exist")
        
        if member_id not in project.member_ids:
            project.member_ids.append(member_id)
            project.save()
        
        return project
    
    @staticmethod
    def remove_member(*, project: Project, user_id: str, member_id: str) -> Project:
        """Remove member from project"""
        
        if str(project.owner_id) != user_id:
            raise PermissionDenied("Only project owner can remove members")
        
        if member_id == str(project.owner_id):
            raise ValidationError("Cannot remove project owner")
        
        if member_id in project.member_ids:
            project.member_ids.remove(member_id)
            project.save()
        
        return project