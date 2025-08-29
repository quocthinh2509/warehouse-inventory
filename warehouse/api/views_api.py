# inventory/views_api.py
from rest_framework import viewsets, mixins, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Prefetch, Q, Sum

from api.models import Product, Warehouse, Item, Inventory, Move
from .serializers import (
    ProductSerializer, WarehouseSerializer,
    ItemSerializer, ItemCreateBySkuSerializer,
    InventorySerializer,
    MoveSerializer, MoveCreateSerializer,
)

class DefaultPerms(permissions.IsAuthenticatedOrReadOnly):
    pass


# ===== Catalog =====
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("sku")
    serializer_class = ProductSerializer
    permission_classes = [DefaultPerms]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["sku", "name", "code4"]
    ordering_fields = ["sku", "name", "code4", "id"]


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all().order_by("code")
    serializer_class = WarehouseSerializer
    permission_classes = [DefaultPerms]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "id"]


# ===== Items =====
class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.select_related("product", "warehouse").all()
    serializer_class = ItemSerializer
    permission_classes = [DefaultPerms]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["barcode_text", "product__sku", "product__name", "warehouse__code"]
    ordering_fields = ["created_at", "seq", "import_date", "status"]

    def get_queryset(self):
        qs = super().get_queryset()
        # filter nhanh
        product = self.request.query_params.get("product")
        sku = self.request.query_params.get("sku")
        wh = self.request.query_params.get("warehouse")
        status_q = self.request.query_params.get("status")
        if product: qs = qs.filter(product_id=product)
        if sku: qs = qs.filter(product__sku__iexact=sku)
        if wh: qs = qs.filter(warehouse_id=wh) if wh.isdigit() else qs.filter(warehouse__code=wh)
        if status_q: qs = qs.filter(status=status_q)
        return qs

    @action(detail=False, methods=["post"], url_path="create-by-sku")
    def create_by_sku(self, request):
        """
        POST /api/items/create-by-sku/
        body: { "sku": "...", "import_date": "YYYY-MM-DD", "mark_in": true, "to_wh_code": "HCM", "note": "" }
        """
        ser = ItemCreateBySkuSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = ser.save()
        return Response(ItemSerializer(item).data, status=status.HTTP_201_CREATED)


# ===== Inventory (read-only) =====
class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventorySerializer
    permission_classes = [DefaultPerms]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["product__sku", "product__name", "warehouse__code"]
    ordering_fields = ["qty"]

    def get_queryset(self):
        qs = Inventory.objects.select_related("product", "warehouse")
        sku = self.request.query_params.get("sku")
        wh = self.request.query_params.get("warehouse")
        if sku: qs = qs.filter(product__sku__iexact=sku)
        if wh: qs = qs.filter(warehouse__code=wh) if not wh.isdigit() else qs.filter(warehouse_id=wh)
        return qs.order_by("-qty", "product__sku")


# ===== Moves =====
class MoveViewSet(viewsets.ModelViewSet):
    queryset = Move.objects.select_related("item", "product", "from_wh", "to_wh").all().order_by("-created_at")
    serializer_class = MoveSerializer
    permission_classes = [DefaultPerms]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "item__barcode_text", "product__sku", "from_wh__code", "to_wh__code", "note", "type_action"
    ]
    ordering_fields = ["created_at", "action"]

    def create(self, request, *args, **kwargs):
        ser = MoveCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        mv = ser.save()
        return Response(MoveSerializer(mv).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request):
        """
        POST /api/moves/bulk/
        body: { "items": [ {MoveCreate payload}, ... ] }
        """
        data = request.data.get("items") or []
        out = []
        for row in data:
            s = MoveCreateSerializer(data=row); s.is_valid(raise_exception=True)
            mv = s.save(); out.append(MoveSerializer(mv).data)
        return Response({"created": len(out), "moves": out}, status=status.HTTP_201_CREATED)
