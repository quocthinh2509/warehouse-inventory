from django.urls import path
from erp_the20.views.shift_view import (
    ShiftTemplateListCreate,
    ShiftTemplateDetail,
    ShiftInstanceListCreate,
    ShiftInstanceDetail,
    ShiftAssignmentCRUD,
    ShiftRegistrationCRUD,
)

urlpatterns = [
    # ===== SHIFT TEMPLATE =====
    path("templates/", ShiftTemplateListCreate.as_view(), name="shift-template-list"),
    path("templates/<int:pk>/", ShiftTemplateDetail.as_view(), name="shift-template-detail"),

    # ===== SHIFT INSTANCE =====
    path("instances/", ShiftInstanceListCreate.as_view(), name="shift-instance-list"),
    path("instances/<int:pk>/", ShiftInstanceDetail.as_view(), name="shift-instance-detail"),

    # ===== SHIFT ASSIGNMENT =====
    path("assignments/", ShiftAssignmentCRUD.as_view(), name="shift-assignment-create"),  # POST
    path("assignments/<int:pk>/", ShiftAssignmentCRUD.as_view(), name="shift-assignment-detail"),  # PUT/DELETE

    # ===== SHIFT REGISTRATION =====
    path("registrations/", ShiftRegistrationCRUD.as_view(), name="shift-registration-create"),  # POST
    path("registrations/<int:pk>/", ShiftRegistrationCRUD.as_view(), name="shift-registration-detail"),  # PUT/DELETE
]
