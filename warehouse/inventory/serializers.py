# inventory/serializers.py
from rest_framework import serializers
from django.db.models import Sum
from .models import Product, Warehouse, Item, Inventory, Move

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name"]

class ProductSerializer(serializers.ModelSerializer):
    quantity = serializers.SerializerMethodField()
    class Meta:
        model = Product
        fields = ["id", "sku", "name", "code4", "quantity"]

    def get_quantity(self, obj):
        total = Inventory.objects.filter(product=obj).aggregate(t=Sum("qty")).get("t")
        return total or 0

class ItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True, required=False
    )
    warehouse = WarehouseSerializer(read_only=True)
    warehouse_id = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), source="warehouse", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Item
        fields = [
            "id","barcode_text","product","product_id","warehouse","warehouse_id",
            "status","created_at","import_date"
        ]
        read_only_fields = ["barcode_text","created_at"]

class InventorySerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    warehouse = WarehouseSerializer()
    class Meta:
        model = Inventory
        fields = ["product","warehouse","qty"]

class MoveSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)
    item_id = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all(), source="item", write_only=True, required=False, allow_null=True
    )
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True, required=False, allow_null=True
    )
    from_wh = WarehouseSerializer(read_only=True)
    from_wh_id = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), source="from_wh", write_only=True, required=False, allow_null=True
    )
    to_wh = WarehouseSerializer(read_only=True)
    to_wh_id = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), source="to_wh", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Move
        fields = [
            "id","created_at","action","item","item_id","product","product_id",
            "quantity","from_wh","from_wh_id","to_wh","to_wh_id",
            "type_action","note","tag","batch_id"
        ]
        read_only_fields = ["created_at"]
