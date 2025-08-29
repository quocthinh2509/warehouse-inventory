from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from .models import Product, Warehouse, Item, Inventory, Move
from .serializers import (
    ProductSerializer, WarehouseSerializer, ItemSerializer, InventorySerializer, MoveSerializer
)
from .views import adjust_inventory, allocate_bulk_out  # dùng lại helper sẵn có

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("id")
    serializer_class = ProductSerializer
    lookup_field = "id"

class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all().order_by("code")
    serializer_class = WarehouseSerializer
    lookup_field = "id"

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.select_related("product","warehouse").all().order_by("-created_at")
    serializer_class = ItemSerializer
    lookup_field = "id"

class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Inventory.objects.select_related("product","warehouse").all()
    serializer_class = InventorySerializer
    lookup_field = "id"

class MoveViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Move.objects.select_related("item__product","product","from_wh","to_wh").all().order_by("-created_at")
    serializer_class = MoveSerializer
    lookup_field = "id"

    # ===== API tạo IN/OUT =====

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def bulk_in(self, request):
        """
        body: { "sku": "ABC", "warehouse_id": 1, "quantity": 10, "type_action": "API", "note": "" }
        """
        sku = request.data.get("sku")
        wh_id = request.data.get("warehouse_id")
        qty = int(request.data.get("quantity") or 0)
        if not sku or not wh_id or qty <= 0:
            return Response({"detail":"Missing/invalid payload"}, status=400)

        product = Product.objects.filter(sku=sku).first()
        wh = Warehouse.objects.filter(id=wh_id).first()
        if not product or not wh:
            return Response({"detail":"Product/Warehouse not found"}, status=404)

        Move.objects.create(
            product=product, quantity=qty, action="IN", to_wh=wh,
            type_action=request.data.get("type_action") or "API",
            note=request.data.get("note") or "", batch_id=request.data.get("batch_id") or ""
        )
        adjust_inventory(product, wh, +qty)
        return Response({"ok": True}, status=201)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def bulk_out(self, request):
        """
        body: { "sku": "ABC", "warehouse_id": 1, "quantity": 7, "allow_consume_itemized": true, "type_action":"API" }
        - Trừ bulk trước, thiếu mới 'bốc' Item (FIFO) nếu allow_consume_itemized=true.
        """
        sku = request.data.get("sku")
        wh_id = request.data.get("warehouse_id")
        qty = int(request.data.get("quantity") or 0)
        allow = bool(request.data.get("allow_consume_itemized"))
        if not sku or not wh_id or qty <= 0:
            return Response({"detail":"Missing/invalid payload"}, status=400)

        product = Product.objects.filter(sku=sku).first()
        wh = Warehouse.objects.filter(id=wh_id).first()
        if not product or not wh:
            return Response({"detail":"Product/Warehouse not found"}, status=404)

        try:
            bulk_used, picked_items = allocate_bulk_out(product, wh, qty, allow_consume_itemized=allow)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        if bulk_used > 0:
            Move.objects.create(
                product=product, quantity=bulk_used, action="OUT", from_wh=wh,
                type_action=request.data.get("type_action") or "API",
                note="OUT bulk (API)", batch_id=request.data.get("batch_id") or ""
            )
            adjust_inventory(product, wh, -bulk_used)

        for it in picked_items:
            Move.objects.create(
                item=it, action="OUT", from_wh=wh,
                type_action=request.data.get("type_action") or "API",
                note="OUT picked item (API)", batch_id=request.data.get("batch_id") or ""
            )
            adjust_inventory(it.product, wh, -1)
            it.warehouse = None
            it.status = "shipped"
            it.save(update_fields=["warehouse","status"])

        return Response({"ok": True, "bulk_used": bulk_used, "picked": [i.barcode_text for i in picked_items]}, status=201)
