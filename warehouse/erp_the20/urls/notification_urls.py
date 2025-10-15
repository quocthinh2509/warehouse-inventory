from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp_the20.views.notification_view import NotificationViewSet

router = DefaultRouter()
router.register(r"", NotificationViewSet, basename="notifications")

urlpatterns = [
    path("", include(router.urls)),
]
