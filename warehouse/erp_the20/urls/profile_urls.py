# erp_the20/urls/profile_urls.py
from rest_framework.routers import DefaultRouter
from erp_the20.views.profile_view import EmployeeProfileViewSet
router = DefaultRouter()
router.register(r'', EmployeeProfileViewSet, basename='')
urlpatterns = router.urls
