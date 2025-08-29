from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet, WarehouseViewSet, ItemViewSet,
    InventoryViewSet, MoveViewSet, StockOrderViewSet
)

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'items', ItemViewSet, basename='item')
router.register(r'inventories', InventoryViewSet, basename='inventory')
router.register(r'moves', MoveViewSet, basename='move')
router.register(r'orders', StockOrderViewSet, basename='order')

urlpatterns = [ path('', include(router.urls)), ]
