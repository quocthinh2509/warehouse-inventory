from django.urls import path
from erp_the20.views.position_view import (
    PositionListCreateView,
    PositionDetailView,
)

urlpatterns = [
    # /api/positions/
    path("", PositionListCreateView.as_view(), name="position-list-create"),
    # /api/positions/<int:pk>/
    path("<int:pk>/", PositionDetailView.as_view(), name="position-detail"),
]
