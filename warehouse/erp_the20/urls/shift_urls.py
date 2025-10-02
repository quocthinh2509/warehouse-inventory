from django.urls import path
from erp_the20.views.shift_view import (
    ShiftTemplateListCreate,
    ShiftTemplateDetail,
    ShiftInstanceListCreate,
    ShiftInstanceDetail,
    ShiftInstancesTodayView
)

urlpatterns = [
    # ===== SHIFT TEMPLATE =====
    path("templates/", ShiftTemplateListCreate.as_view(), name="shift-template-list"),
    path("templates/<int:pk>/", ShiftTemplateDetail.as_view(), name="shift-template-detail"),

    # ===== SHIFT INSTANCE =====
    path("instances/", ShiftInstanceListCreate.as_view(), name="shift-instance-list"),
    path("instances/<int:pk>/", ShiftInstanceDetail.as_view(), name="shift-instance-detail"),

    path("instances/today/", ShiftInstanceListCreate.as_view(), name="shift-instance-today"),
]
