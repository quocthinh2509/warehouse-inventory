# -*- coding: utf-8 -*-
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp_the20.views.leave_view import LeaveRequestViewSet

# Dùng DefaultRouter (có trang index). Nếu không muốn trang index, dùng SimpleRouter().
router = DefaultRouter()
# => /leave-requests/ ...
router.register(r"leave-requests", LeaveRequestViewSet, basename="leave-requests")

app_name = "leave"

urlpatterns = [
    # tạo toàn bộ routes cho LeaveRequestViewSet:
    #   POST   /leave-requests/
    #   PUT    /leave-requests/{id}/
    #   DELETE /leave-requests/{id}/
    #   PUT    /leave-requests/{id}/submit/
    #   PUT    /leave-requests/{id}/cancel/
    #   PUT    /leave-requests/{id}/decide/
    #   GET    /leave-requests/my/
    #   GET    /leave-requests/pending/
    #   GET    /leave-requests/search/
    path("", include(router.urls)),
]
