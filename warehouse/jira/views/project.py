# ============================================
# jira/views/project.py
# ============================================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from jira.serializers.project import (
    ProjectCreateSerializer,
    ProjectUpdateSerializer,
    ProjectOutputSerializer
)
from jira.selectors.project import ProjectSelector
from jira.services.project import ProjectService


class ProjectPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProjectListCreateAPIView(APIView):
    """
    GET: List all projects for current user
    POST: Create a new project
    
    Query params (GET):
    - page: int
    - page_size: int
    
    Request body (POST):
    - name: string (required)
    - key: string (required, max 10 chars, unique)
    - description: string (optional)
    - member_ids: list of UUID (optional)
    """
    
    def get(self, request):
        user_id = str(request.user.id)  # Assuming you have auth middleware
        
        projects = ProjectSelector.get_projects_list(user_id=user_id)
        
        # Paginate
        paginator = ProjectPagination()
        page = paginator.paginate_queryset(projects, request)
        
        # Enrich with user data
        projects_with_users = ProjectSelector.enrich_projects_with_users(page)
        
        serializer = ProjectOutputSerializer(projects_with_users, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        project = ProjectService.create_project(
            owner_id=str(request.user.id),
            **serializer.validated_data
        )
        
        # Enrich and return
        projects_with_users = ProjectSelector.enrich_projects_with_users([project])
        output_serializer = ProjectOutputSerializer(projects_with_users[0])
        
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ProjectDetailAPIView(APIView):
    """
    GET: Retrieve project details
    PUT: Update project
    DELETE: Delete project
    
    Path params:
    - project_id: int
    """
    
    def get(self, request, project_id):
        project = ProjectSelector.get_project_by_id(project_id)
        
        if not project:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        projects_with_users = ProjectSelector.enrich_projects_with_users([project])
        serializer = ProjectOutputSerializer(projects_with_users[0])
        
        return Response(serializer.data)
    
    def put(self, request, project_id):
        project = ProjectSelector.get_project_by_id(project_id)
        
        if not project:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ProjectUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        updated_project = ProjectService.update_project(
            project=project,
            user_id=str(request.user.id),
            **serializer.validated_data
        )
        
        projects_with_users = ProjectSelector.enrich_projects_with_users([updated_project])
        output_serializer = ProjectOutputSerializer(projects_with_users[0])
        
        return Response(output_serializer.data)
    
    def delete(self, request, project_id):
        project = ProjectSelector.get_project_by_id(project_id)
        
        if not project:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        ProjectService.delete_project(
            project=project,
            user_id=str(request.user.id)
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
