from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.models import (
    Product, Warehouse, Item, Inventory, Move,
    StockOrder, StockOrderLine
)
from api.serializers import (
    ProductSerializer, WarehouseSerializer, ItemSerializer,
    InventorySerializer, MoveSerializer,
    StockOrderSerializer, StockOrderLineWriteSerializer, StockOrderLineReadSerializer
)

# --- CRUD cơ bản ---
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("id")
    serializer_class = ProductSerializer

class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all().order_by("code")
    serializer_class = WarehouseSerializer

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all().select_related("product", "warehouse")
    serializer_class = ItemSerializer

class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Inventory.objects.select_related("product", "warehouse").all()
    serializer_class = InventorySerializer


class MoveViewSet(viewsets.ModelViewSet):
    queryset = Move.objects.select_related("item", "product", "from_wh", "to_wh").all()
    serializer_class = MoveSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        move = serializer.save()
        move.apply()  # áp tồn kho & cập nhật trạng thái item


# --- STOCK ORDER ---
class StockOrderViewSet(viewsets.ModelViewSet):
    queryset = StockOrder.objects.select_related("from_wh", "to_wh", "created_by").prefetch_related("lines").all()
    serializer_class = StockOrderSerializer

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def confirm(self, request, pk=None):
        """
        POST /api/orders/{id}/confirm/
        -> gọi StockOrder.confirm() để sinh Move & cập nhật tồn kho
        """
        order = self.get_object()
        if order.is_confirmed:
            return Response({"detail": "Đơn đã xác nhận."}, status=status.HTTP_200_OK)
        batch_id = request.data.get("batch_id", f"ORDER-{order.id}")
        order.confirm(batch_id=batch_id)
        ser = self.get_serializer(order)
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def add_line(self, request, pk=None):
        """
        POST /api/orders/{id}/add_line/
        body: {item_id? or product_id+quantity, note?}
        """
        order = self.get_object()
        if order.is_confirmed:
            return Response({"detail": "Đơn đã xác nhận, không thể thêm dòng."},
                            status=status.HTTP_400_BAD_REQUEST)

        ser = StockOrderLineWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        StockOrderLine.objects.create(order=order, **ser.validated_data)
        return Response({"detail": "Đã thêm dòng."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def remove_line(self, request, pk=None):
        """
        POST /api/orders/{id}/remove_line/
        body: {line_id}
        """
        order = self.get_object()
        line_id = request.data.get("line_id")
        try:
            line = order.lines.get(id=line_id)
        except StockOrderLine.DoesNotExist:
            return Response({"detail": "Không tìm thấy dòng."}, status=status.HTTP_404_NOT_FOUND)
        if order.is_confirmed:
            return Response({"detail": "Đơn đã xác nhận, không thể xoá dòng."},
                            status=status.HTTP_400_BAD_REQUEST)
        line.delete()
        return Response({"detail": "Đã xoá dòng."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def lines(self, request, pk=None):
        """GET /api/orders/{id}/lines/ -> trả list dòng (đọc)."""
        order = self.get_object()
        ser = StockOrderLineReadSerializer(order.lines.all(), many=True)
        return Response(ser.data)
