# -*- coding: utf-8 -*-
from __future__ import annotations
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp_the20.views.leave_view import LeaveRequestViewSet

app_name = "leave"

router = DefaultRouter()
router.register(r"requests", LeaveRequestViewSet, basename="leave-requests")

urlpatterns = [
    path("", include(router.urls)),
]
