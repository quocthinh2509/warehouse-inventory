# ============================================
# jira/urls.py
# ============================================
from django.urls import path
from jira.views.project import (
    ProjectListCreateAPIView,
    ProjectDetailAPIView
)
from jira.views.issue import (
    IssueListCreateAPIView,
    IssueDetailAPIView
)
from jira.views.comment import (
    CommentListCreateAPIView,
    CommentDetailAPIView
)

app_name = 'jira'

urlpatterns = [
    # Projects
    path('projects/', ProjectListCreateAPIView.as_view(), name='project-list-create'),
    path('projects/<int:project_id>/', ProjectDetailAPIView.as_view(), name='project-detail'),
    
    # Issues
    path('issues/', IssueListCreateAPIView.as_view(), name='issue-list-create'),
    path('issues/<int:issue_id>/', IssueDetailAPIView.as_view(), name='issue-detail'),
    
    # Comments
    path('issues/<int:issue_id>/comments/', CommentListCreateAPIView.as_view(), name='comment-list-create'),
    path('comments/<int:comment_id>/', CommentDetailAPIView.as_view(), name='comment-detail'),
]