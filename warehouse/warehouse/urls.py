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
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from inventory import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Dashboard & điều hướng chính
    path("", views.index, name="index"),

    # Tạo tem, quét di chuyển
    path("generate/", views.generate_labels, name="generate_labels"),
    path("labels/download/<slug:batch>/", views.download_batch, name="download_batch"),
    path("scan-move/", views.scan_move, name="scan_move"),

    # Phân tích & tra cứu
    path("dashboard/", views.dashboard, name="dashboard"),
    path("inventory/", views.inventory_view, name="inventory"),
    path("transactions/", views.transactions, name="transactions"),
    path("barcode-lookup/", views.barcode_lookup, name="barcode_lookup"),

    # CRUD Product
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_update, name="product_update"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    # Query Panel (thêm/sửa/lưu/execute)
    path("queries/", views.query_panel, name="query_panel"),
    path("queries/<int:pk>/", views.query_panel, name="query_panel_edit"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
