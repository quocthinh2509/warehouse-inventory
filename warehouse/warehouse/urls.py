"""
URL configuration for warehouse project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# warehouse/urls.py
# warehouse/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from inventory import views
from rest_framework.routers import DefaultRouter
from inventory.views_api import (
    ProductViewSet, WarehouseViewSet, ItemViewSet, InventoryViewSet, MoveViewSet
)

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'warehouses', WarehouseViewSet)
router.register(r'items', ItemViewSet)
router.register(r'inventories', InventoryViewSet, basename="inventory")
router.register(r'moves', MoveViewSet, basename="move")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    # Vào web -> Generate
    path("", views.dashboard_redirect, name="dashboard"),

# Đối với quy trình nhập tay, google sheet , API
    path("manual/start/", views.manual_start, name="manual_start"),
    path("manual/add/", views.manual_add_line, name="manual_add_line"),
    path("manual/clear/", views.manual_clear, name="manual_clear"),
    path("manual/remove/<int:idx>/", views.manual_remove_line, name="manual_remove_line"),
    path("manual/preview/", views.manual_preview, name="manual_preview"),
    path("manual/finalize/", views.manual_finalize, name="manual_finalize"),
    path("manual/batch/", views.manual_batch_detail, name="manual_batch_detail"),   



# Đối với items có barcode 
    # Generate & giỏ in
    path("scan-check/generate/", views.generate_labels, name="generate_labels"),
    path("scan-check/generate/clear/", views.clear_queue, name="clear_queue"),
    path("scan-check/generate/remove/<int:idx>/", views.remove_queue_line, name="remove_queue_line"),
    path("scan-check/generate/finalize/", views.finalize_queue, name="finalize_queue"),
    # Tải ZIP
    path("labels/download/<slug:batch>/", views.download_batch, name="download_batch"),

    # Scan & Check 
    path("scan-check/scan/", views.scan_move, name="scan_scan"),
    path("scan-check/scan/start/", views.scan_start, name="scan_start"),
    path("scan-check/scan/stop/", views.scan_stop, name="scan_stop"),
    path("scan-check/check/", views.barcode_lookup, name="scan_check"),


    # Dashboard
    path("dashboard/", views.dashboard_redirect, name="dashboard"),  # click menu -> mặc định vào warehouse
    path("dashboard/warehouse/", views.dashboard_warehouse, name="dashboard_warehouse"),
    path("dashboard/barcodes/", views.dashboard_barcodes, name="dashboard_barcodes"),
    path("dashboard/history/", views.dashboard_history, name="dashboard_history"),
    # Config hub
    path("config/", views.config_index, name="config_index"),

    # Phân tích & tra cứu
    path("inventory/", views.inventory_view, name="inventory"),
    path("transactions/", views.transactions, name="transactions"),
    path("barcode-lookup/", views.barcode_lookup, name="barcode_lookup"),

    # CRUD Product
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_update, name="product_update"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    # Query Panel
    path("queries/", views.query_panel, name="query_panel"),
    path("queries/<int:pk>/", views.query_panel, name="query_panel_edit"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
