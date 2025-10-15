from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp_the20.views.handover_view import HandoverViewSet, HandoverItemViewSet

router = DefaultRouter()
router.register(r"", HandoverViewSet, basename="handover")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "items/set-status/",
        HandoverItemViewSet.as_view({"post": "set_status"}),
        name="handover_item_set_status",
    ),
]
