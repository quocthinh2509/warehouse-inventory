from rest_framework import serializers
from .models import Product, Warehouse, Item, Inventory, Move

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = "__all__"

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = "__all__"

class InventorySerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    warehouse = WarehouseSerializer(read_only=True)
    class Meta:
        model = Inventory
        fields = "__all__"

class MoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Move
        fields = "__all__"
