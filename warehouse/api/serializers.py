from rest_framework import serializers
from .models import (
    Product, Warehouse, Item, Inventory, Move,
    StockOrder, StockOrderLine
)

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


# ----- MOVE -----
class MoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Move
        fields = "__all__"

    def validate(self, attrs):
        # dùng clean() của model để bảo đảm quy tắc
        inst = Move(**attrs)
        inst.clean()
        return attrs


# ----- STOCK ORDER -----
class StockOrderLineWriteSerializer(serializers.ModelSerializer):
    """
    Dùng cho ghi (POST/PUT). Một dòng phải:
    - có item (barcode) và KHÔNG có product/quantity, hoặc
    - có product + quantity và KHÔNG có item.
    """
    item_id = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all(), source="item", required=False, allow_null=True
    )
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", required=False, allow_null=True
    )

    class Meta:
        model = StockOrderLine
        fields = ["id", "item_id", "product_id", "quantity", "note"]

    def validate(self, attrs):
        item = attrs.get("item")
        product = attrs.get("product")
        qty = attrs.get("quantity")
        if item and (product or qty):
            raise serializers.ValidationError("Chỉ chọn Item HOẶC Product+Quantity.")
        if (not item) and (not product or not qty):
            raise serializers.ValidationError("Thiếu dữ liệu: cần Item hoặc Product+Quantity.")
        return attrs


class StockOrderLineReadSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)
    product = ProductSerializer(read_only=True)

    class Meta:
        model = StockOrderLine
        fields = ["id", "item", "product", "quantity", "note"]


class StockOrderSerializer(serializers.ModelSerializer):
    """
    Đơn hàng đọc/ghi có nested lines.
    - Khi POST/PUT, truyền lines như StockOrderLineWriteSerializer (item_id/product_id).
    - Khi GET, trả về đầy đủ object của dòng.
    """
    lines = StockOrderLineWriteSerializer(many=True, write_only=True, required=False)
    lines_read = StockOrderLineReadSerializer(many=True, read_only=True, source="lines")

    from_wh_id = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), source="from_wh", required=False, allow_null=True
    )
    to_wh_id = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), source="to_wh", required=False, allow_null=True
    )

    class Meta:
        model = StockOrder
        fields = [
            "id", "order_type", "source", "reference", "note",
            "from_wh_id", "to_wh_id",
            "created_by", "created_at", "confirmed_at", "is_confirmed",
            "lines", "lines_read",
        ]
        read_only_fields = ["created_by", "created_at", "confirmed_at", "is_confirmed"]

    def validate(self, attrs):
        ot = attrs.get("order_type") or getattr(self.instance, "order_type", None)
        from_wh = attrs.get("from_wh", getattr(self.instance, "from_wh", None))
        to_wh = attrs.get("to_wh", getattr(self.instance, "to_wh", None))

        if ot == "IN" and not to_wh:
            raise serializers.ValidationError("Đơn IN cần to_wh (kho nhận).")
        if ot == "OUT" and not from_wh:
            raise serializers.ValidationError("Đơn OUT cần from_wh (kho xuất).")
        return attrs

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        user = self.context["request"].user if self.context.get("request") else None
        order = StockOrder.objects.create(created_by=user, **validated_data)
        for ld in lines_data:
            StockOrderLine.objects.create(order=order, **ld)
        return order

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()

        if lines_data is not None:
            # đơn giản: xoá toàn bộ rồi tạo lại (có thể tối ưu patch sau)
            instance.lines.all().delete()
            for ld in lines_data:
                StockOrderLine.objects.create(order=instance, **ld)
        return instance
