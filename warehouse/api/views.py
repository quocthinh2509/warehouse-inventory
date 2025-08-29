# inventory/views_api.py
from rest_framework import viewsets
from api.models import Product, Warehouse, Item, Inventory, Move
from api.serializers import ProductSerializer, WarehouseSerializer, ItemSerializer, InventorySerializer, MoveSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer

class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer

class MoveViewSet(viewsets.ModelViewSet):
    queryset = Move.objects.all()
    serializer_class = MoveSerializer
