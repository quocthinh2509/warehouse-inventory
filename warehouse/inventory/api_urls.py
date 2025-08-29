# inventory/api_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    WarehouseViewSet, ProductViewSet, ItemViewSet,
    InventoryView, HistoryView, HistoryStatsView, HistoryUpdatesView,
    ManualBatchView, ScanView, GenerateLabelsView
)

router = DefaultRouter()
router.register(r"warehouses", WarehouseViewSet, basename="warehouses")
router.register(r"products", ProductViewSet, basename="products")
router.register(r"items", ItemViewSet, basename="items")

urlpatterns = [
    path("", include(router.urls)),

    # Inventory (tổng hợp)
    path("inventory/", InventoryView.as_view(), name="api_inventory"),

    # History + stats + updates
    path("history/", HistoryView.as_view(), name="api_history"),
    path("history/stats/", HistoryStatsView.as_view(), name="api_history_stats"),
    path("history/updates/", HistoryUpdatesView.as_view(), name="api_history_updates"),

    # Manual batch (session)
    path("manual/start", ManualBatchView.as_view(), name="api_manual_start"),
    path("manual/preview", ManualBatchView.as_view(), name="api_manual_preview"),
    path("manual/lines", ManualBatchView.as_view(), name="api_manual_lines"),
    path("manual/clear", ManualBatchView.as_view(), name="api_manual_clear"),
    path("manual/finalize", ManualBatchView.as_view(), name="api_manual_finalize"),
    path("manual/upload", ManualBatchView.as_view(), name="api_manual_upload"),

    # Scan session
    path("scan/start", ScanView.as_view(), name="api_scan_start"),
    path("scan/stop", ScanView.as_view(), name="api_scan_stop"),
    path("scan/scan", ScanView.as_view(), name="api_scan_scan"),
    path("scan/state", ScanView.as_view(), name="api_scan_state"),

    # Generate labels (one-shot, không dùng session)
    path("generate/labels", GenerateLabelsView.as_view(), name="api_generate_labels"),
]
