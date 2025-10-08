from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp_the20.views.shift_view import ShiftTemplateViewSet

router = DefaultRouter()
router.register(r"shift-templates", ShiftTemplateViewSet, basename="shift-template")

urlpatterns = [
    path("", include(router.urls)),
]
