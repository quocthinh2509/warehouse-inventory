from django.urls import path, include
from rest_framework.routers import DefaultRouter
from erp_the20.views.proposal_view import ProposalViewSet

router = DefaultRouter()
router.register(r"", ProposalViewSet, basename="proposals")

urlpatterns = [
    path("", include(router.urls)),
]
