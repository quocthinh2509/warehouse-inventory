# ============================================
# jira/selectors/project.py
# ============================================
from typing import List, Optional
from django.db.models import QuerySet, Prefetch
from jira.models import Project, Status
from jira.clients.user_client import UserServiceClient


class ProjectSelector:
    
    @staticmethod
    def get_project_by_id(project_id: int) -> Optional[Project]:
        """Get single project by ID"""
        try:
            return Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return None
    
    @staticmethod
    def get_project_by_key(key: str) -> Optional[Project]:
        """Get project by key"""
        try:
            return Project.objects.get(key=key)
        except Project.DoesNotExist:
            return None
    
    @staticmethod
    def get_projects_by_user(user_id: str) -> QuerySet:
        """Get all projects where user is owner or member"""
        return Project.objects.filter(
            models.Q(owner_id=user_id) | models.Q(member_ids__contains=user_id)
        ).distinct()
    
    @staticmethod
    def get_projects_list(user_id: str = None) -> QuerySet:
        """Get paginated projects list"""
        queryset = Project.objects.all()
        
        if user_id:
            queryset = queryset.filter(
                models.Q(owner_id=user_id) | models.Q(member_ids__contains=user_id)
            ).distinct()
        
        return queryset
    
    @staticmethod
    def enrich_projects_with_users(projects: List[Project]) -> List[Project]:
        """Fetch and attach user data to projects"""
        user_ids = set()
        
        for project in projects:
            user_ids.add(str(project.owner_id))
            user_ids.update([str(uid) for uid in project.member_ids])
        
        users_dict = UserServiceClient.get_users_by_ids(list(user_ids))
        
        for project in projects:
            project.owner_data = users_dict.get(str(project.owner_id))
            project.members_data = [
                users_dict.get(str(uid))
                for uid in project.member_ids
                if users_dict.get(str(uid))
            ]
        
        return projects
