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
from inventory import views_api_duplicate as api_views
from rest_framework.routers import DefaultRouter

from inventory.views_api import (
    ProductViewSet, WarehouseViewSet, ItemViewSet,
    InventoryViewSet, MoveViewSet,
    StockOrderViewSet
)

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'warehouses', WarehouseViewSet)
router.register(r'items', ItemViewSet)
router.register(r'inventories', InventoryViewSet, basename="inventory")
router.register(r'moves', MoveViewSet, basename="move")
router.register(r'orders', StockOrderViewSet, basename="order")

# Duplicate router for /api/api/ endpoints
router_v2 = DefaultRouter()
router_v2.register(r'products', ProductViewSet)
router_v2.register(r'warehouses', WarehouseViewSet)
router_v2.register(r'items', ItemViewSet)
router_v2.register(r'inventories', InventoryViewSet, basename="inventory")
router_v2.register(r'moves', MoveViewSet, basename="move")
router_v2.register(r'orders', StockOrderViewSet, basename="order")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/api/", include(router_v2.urls)),
    
    # ========== API Duplicate Routes ==========
    # Main & Dashboard API endpoints
    path("api/index/", api_views.api_index, name="api_index"),
    path("api/config/", api_views.api_config_index, name="api_config_index"),
    path("api/dashboard/", api_views.api_dashboard_redirect, name="api_dashboard_redirect"),
    path("api/dashboard/warehouse/", api_views.api_dashboard_warehouse, name="api_dashboard_warehouse"),
    path("api/dashboard/barcodes/", api_views.api_dashboard_barcodes, name="api_dashboard_barcodes"),
    path("api/dashboard/history/", api_views.api_dashboard_history, name="api_dashboard_history"),
    
    # Manual Process API endpoints
    path("api/manual/start/", api_views.api_manual_start, name="api_manual_start"),
    path("api/manual/add/", api_views.api_manual_add_line, name="api_manual_add_line"),
    path("api/manual/clear/", api_views.api_manual_clear, name="api_manual_clear"),
    path("api/manual/remove/<int:idx>/", api_views.api_manual_remove_line, name="api_manual_remove_line"),
    path("api/manual/preview/", api_views.api_manual_preview, name="api_manual_preview"),
    path("api/manual/finalize/", api_views.api_manual_finalize, name="api_manual_finalize"),
    path("api/manual/batch/", api_views.api_manual_batch_detail, name="api_manual_batch_detail"),
    path("api/manual/upload/", api_views.api_manual_upload, name="api_manual_upload"),
    path("api/manual/sample.csv", api_views.api_manual_sample_csv, name="api_manual_sample_csv"),
    
    # Generate & Scan API endpoints
    path("api/scan-check/generate/", api_views.api_generate_labels, name="api_generate_labels"),
    path("api/scan-check/generate/clear/", api_views.api_clear_queue, name="api_clear_queue"),
    path("api/scan-check/generate/remove/<int:idx>/", api_views.api_remove_queue_line, name="api_remove_queue_line"),
    path("api/scan-check/generate/finalize/", api_views.api_finalize_queue, name="api_finalize_queue"),
    path("api/labels/download/<slug:batch>/", api_views.api_download_batch, name="api_download_batch"),
    path("api/scan-check/scan/", api_views.api_scan_move, name="api_scan_move"),
    path("api/scan-check/scan/start/", api_views.api_scan_start, name="api_scan_start"),
    path("api/scan-check/scan/stop/", api_views.api_scan_stop, name="api_scan_stop"),
    path("api/scan-check/check/", api_views.api_barcode_lookup, name="api_scan_check"),
    
    # Analysis & Lookup API endpoints
    path("api/inventory/", api_views.api_inventory_view, name="api_inventory"),
    path("api/transactions/", api_views.api_transactions, name="api_transactions"),
    path("api/barcode-lookup/", api_views.api_barcode_lookup, name="api_barcode_lookup"),
    
    # Product CRUD API endpoints
    path("api/products/", api_views.api_product_list, name="api_product_list"),
    path("api/products/new/", api_views.api_product_create, name="api_product_create"),
    path("api/products/<int:pk>/edit/", api_views.api_product_update, name="api_product_update"),
    path("api/products/<int:pk>/delete/", api_views.api_product_delete, name="api_product_delete"),
    
    # Query Panel API endpoints
    path("api/queries/", api_views.api_query_panel, name="api_query_panel"),
    path("api/queries/<int:pk>/", api_views.api_query_panel, name="api_query_panel_edit"),
    
    # Export API endpoints
    path("api/export/barcodes/csv/", api_views.api_export_barcodes_csv, name="api_export_barcodes_csv"),
    path("api/export/history/csv/", api_views.api_export_history_csv, name="api_export_history_csv"),
    
    # ========== End API Duplicate Routes ==========
    
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
    path("manual/upload/", views.manual_upload, name="manual_upload"),
    path("manual/sample.csv", views.manual_sample_csv, name="manual_sample_csv"),


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
