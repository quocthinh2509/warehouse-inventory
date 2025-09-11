# inventory/api_views.py
from datetime import datetime, timedelta
import logging
import tempfile
from django.utils import timezone
from django.db.models import Q, Sum, Max, Count, F, IntegerField, CharField, Case, When, Value
from django.db import transaction, IntegrityError
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest
from django.conf import settings
from pathlib import Path
import csv, io, re, zipfile
# thêm import (trên đầu file)
from django.db.models.deletion import ProtectedError
from .utils import save_code128_png

from rest_framework import viewsets, mixins, status
from rest_framework.views import APIView
from collections import defaultdict
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.exceptions import ValidationError
from .pagination import PageLimitPagination

from .models import Product, Warehouse, Item, Inventory, Move, StockOrder, StockOrderLine
from .serializers import (
    ProductSerializer, WarehouseSerializer, ItemSerializer,
    InventorySerializer, MoveSerializer,
    BatchTagSuggestInputSerializer, BatchTagSuggestOutputSerializer,
)

# === import helpers từ views.py (giữ nguyên file gốc) ===
from .views import (
    adjust_inventory, _manual_batch, _save_manual_batch,
    preview_bulk_out, allocate_bulk_out,
    _scan_state, _save_scan_state, _tag_max_today,
    _parse_manual_file, _merge_lines,
    export_barcodes_csv, export_history_csv
)

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
logger = logging.getLogger("inventory.scan")

# ---------- CRUD cơ bản ----------
# thay class WarehouseViewSet hiện tại bằng phiên bản CRUD
class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all().order_by("code")
    serializer_class = WarehouseSerializer
    pagination_class = PageLimitPagination
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        return qs

    # Trả lỗi 409 khi bị ràng buộc PROTECT thay vì văng lỗi 500
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Kho đang được tham chiếu (Item/Inventory/Move). Không thể xoá."},
                status=409,
            )
        except IntegrityError:
            return Response({"detail": "Không thể xoá do ràng buộc CSDL."}, status=409)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("sku")
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    pagination_class = PageLimitPagination


    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(sku__icontains=q)|Q(name__icontains=q)|Q(code4__icontains=q))
        return qs

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Sản phẩm đang được tham chiếu (Item/Inventory/Move). Không thể xoá."},
                status=409,
            )
        except IntegrityError:
            return Response({"detail": "Không thể xoá do ràng buộc CSDL."}, status=409)


class ItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Item.objects.select_related("product","warehouse").order_by("-created_at")
    serializer_class = ItemSerializer
    permission_classes = [AllowAny]


    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q","").strip()
        wh = self.request.query_params.get("wh") or ""
        status_ = self.request.query_params.get("status","").strip()
        date_from = self.request.query_params.get("date_from","").strip()
        date_to = self.request.query_params.get("date_to","").strip()

        if q:
            qs = qs.filter(
                Q(barcode_text__icontains=q)|
                Q(product__sku__icontains=q)|
                Q(product__name__icontains=q)|
                Q(product__code4__icontains=q)
            )
        if wh:
            qs = qs.filter(warehouse_id=wh)
        if status_:
            qs = qs.filter(status=status_)
        if date_from:
            try:
                qs = qs.filter(created_at__date__gte=datetime.strptime(date_from, "%Y-%m-%d").date())
            except ValueError:
                pass
        if date_to:
            try:
                qs = qs.filter(created_at__date__lte=datetime.strptime(date_to, "%Y-%m-%d").date())
            except ValueError:
                pass
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())

        # ======= Summary counts =======
        today = timezone.now().date()

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 10))
        total_records = qs.count()
        total_pages = (total_records + page_size - 1) // page_size
        start = (page - 1) * page_size
        end = start + page_size
        paginated_qs = qs[start:end]

        serializer = self.get_serializer(paginated_qs, many=True)


        summary = {
            "total_barcodes": qs.count(),  # tổng barcode
            "in_warehouse": qs.filter(warehouse__isnull=False).count(),  # trong kho (có warehouse)
            "out": qs.filter(status="out").count(),  # đã xuất (status = out)
            "created_today": qs.filter(created_at__date=today).count(),  # tạo hôm nay
            "total_skus": qs.values("product__sku").distinct().count(),  # tổng SKU khác nhau
            "warehouses_with_items": qs.exclude(warehouse__isnull=True).values("warehouse_id").distinct().count(),  # số kho có hàng
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_records": total_records
            }
        }

        # ======= Pagination + serializer =======
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "results": serializer.data,
                "summary": summary
            })

        serializer = self.get_serializer(qs, many=True)
        return Response({
            "results": serializer.data,
            "summary": summary
        })

    @action(detail=False, methods=["get"])
    def export_csv(self, request):
        qs = self.get_queryset()
        # trả file CSV stream y hệt dashboard_barcodes
        return export_barcodes_csv(qs)


class BulkOutBySkuView(APIView):
    """
    POST /api/bulk/out-by-sku
    Body JSON:
    {
      "warehouse_code": "WH1" | null,    # hoặc dùng warehouse_id
      "warehouse_id": 1,
      "lines": [
        {"sku": "SKU001", "qty": 10},
        {"sku": "SKU002", "qty": 5}
      ],
      "reference": "SO-123",            # optional
      "external_id": "EXT-1",           # optional, unique → idempotent
      "note": "Xuất hàng API"            # optional
    }
    Tác dụng: tạo 1 StockOrder OUT (source=API), sinh Move bulk theo SKU và cập nhật Inventory.
    An toàn trong transaction. Sẽ fail nếu thiếu tồn kho.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        wh_id = data.get("warehouse_id")
        wh_code = data.get("warehouse_code")
        reference = (data.get("reference") or "").strip()
        external_id = (data.get("external_id") or "").strip() or None
        note = (data.get("note") or "").strip()
        lines = data.get("lines") or []

        # Compatibility: accept { items: [{sku, qty}], createdTime }
        # - If "lines" is missing but "items" provided, map items -> lines
        if (not lines) and isinstance(data.get("items"), list):
            mapped = []
            for it in data.get("items", []):
                if not isinstance(it, dict):
                    continue
                sku = str((it.get("sku") or "").strip())
                # support qty or quantity
                try:
                    qty = int(it.get("qty") if it.get("qty") is not None else it.get("quantity") or 0)
                except Exception:
                    qty = 0
                mapped.append({"sku": sku, "qty": qty})
            lines = mapped

        # If createdTime supplied and reference empty, place it into reference; otherwise append to note
        created_time = data.get("createdTime") or data.get("created_time")
        if created_time:
            ct = str(created_time)
            if not reference:
                reference = ct
            else:
                note = (note + (" | " if note else "") + f"createdTime={ct}")[:255]

        # Resolve warehouse (auto-create by code if not exists)
        wh = None
        if wh_id:
            wh = Warehouse.objects.filter(id=wh_id).first()
        if not wh and wh_code:
            wh = Warehouse.objects.filter(code=wh_code).first()
            if not wh:
                # Auto-create warehouse with given code
                wh = Warehouse.objects.create(code=wh_code, name=wh_code)
        if not wh:
            return Response({"detail": "Kho không hợp lệ (cần warehouse_code hoặc warehouse_id)."}, status=400)

        # Validate lines
        if not isinstance(lines, list) or not lines:
            return Response({"detail": "Thiếu lines."}, status=400)

        # Preload products by SKU
        skus = [str((ln.get("sku") or "").strip()) for ln in lines]
        qtys = []
        for ln in lines:
            try:
                q = int(ln.get("qty") or 0)
            except Exception:
                q = 0
            qtys.append(q)
        if any((not s) for s in skus) or any(q <= 0 for q in qtys):
            return Response({"detail": "Mỗi dòng cần sku và qty>0."}, status=400)

        products = {p.sku: p for p in Product.objects.filter(sku__in=skus)}
        missing = [s for s in skus if s not in products]
        # Auto-create missing products (name = sku)
        if missing:
            for m in sorted(set(missing)):
                if not m:
                    continue
                p = Product.objects.create(sku=m, name=m)
                products[p.sku] = p

        # Group by SKU to sum quantities (avoid duplicates)
        grouped = {}
        for sku, qty in zip(skus, qtys):
            grouped[sku] = grouped.get(sku, 0) + int(qty)

        try:
            with transaction.atomic():
                if external_id:
                    # Idempotent create guarded by unique(external_id)
                    order, created = StockOrder.objects.get_or_create(
                        external_id=external_id,
                        defaults={
                            "order_type": "OUT",
                            "source": "API",
                            "reference": reference,
                            "note": note,
                            "from_wh": wh,
                        },
                    )
                    if not created:
                        return Response({
                            "detail": "EXISTS",
                            "order_id": order.id,
                            "warehouse": (order.from_wh or order.to_wh).code if (order.from_wh or order.to_wh) else None,
                            "lines": [
                                {"sku": ln.product.sku, "qty": ln.quantity}
                                for ln in order.lines.all() if ln.product_id and ln.quantity
                            ],
                            "skipped": True,
                        }, status=200)
                else:
                    order = StockOrder.objects.create(
                        order_type="OUT",
                        source="API",
                        reference=reference,
                        external_id=external_id,
                        note=note,
                        from_wh=wh,
                    )

                # If we reach here and the order is newly created, add lines and confirm
                if not order.lines.exists():
                    for sku, total_qty in grouped.items():
                        StockOrderLine.objects.create(
                            order=order,
                            product=products[sku],
                            quantity=total_qty,
                            note=note,
                        )
                    order.confirm(batch_id=f"API-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}")

            # Build response summary
            result_lines = [{"sku": sku, "qty": qty} for sku, qty in grouped.items()]
            return Response({
                "detail": "OK",
                "order_id": order.id,
                "warehouse": wh.code,
                "lines": result_lines,
            }, status=201)
        except IntegrityError:
            if external_id:
                # Concurrent create hit unique(external_id). Treat as idempotent success.
                existing = StockOrder.objects.filter(external_id=external_id).first()
                if existing:
                    return Response({
                        "detail": "EXISTS",
                        "order_id": existing.id,
                        "warehouse": (existing.from_wh or existing.to_wh).code if (existing.from_wh or existing.to_wh) else None,
                        "lines": [
                            {"sku": ln.product.sku, "qty": ln.quantity}
                            for ln in existing.lines.all() if ln.product_id and ln.quantity
                        ],
                        "skipped": True,
                    }, status=200)
            return Response({"detail": "Database integrity error."}, status=400)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


class BulkImportOrdersView(APIView):
    """
    POST /api/bulk/import-orders
    Body JSON:
    {
      "orders": [
        {
          "external_id": "EXT-1",             # unique, dùng làm idempotency key
          "order_type": "OUT" | "IN",         # mặc định OUT nếu thiếu
          "warehouse_code": "WH1",            # hoặc warehouse_id
          "warehouse_id": 1,
          "reference": "SO-1",
          "note": "..",
          "lines": [ {"sku": "A", "qty": 2}, {"sku": "B", "qty": 3} ]
        },
        { ... }
      ]
    }
    - Tự tạo Warehouse/Product nếu chưa có.
    - Nếu external_id đã tồn tại → bỏ qua tạo mới, trả về trạng thái skipped.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        orders = payload.get("orders") or []
        if not isinstance(orders, list) or not orders:
            return Response({"detail": "Thiếu orders."}, status=400)

        results = []
        for od in orders:
            try:
                wh_id = od.get("warehouse_id")
                wh_code = od.get("warehouse_code")
                reference = (od.get("reference") or "").strip()
                external_id = (od.get("external_id") or "").strip() or None
                note = (od.get("note") or "").strip()
                order_type = (od.get("order_type") or "OUT").upper()
                lines = od.get("lines") or []

                # Resolve warehouse (auto-create)
                wh = None
                if wh_id:
                    wh = Warehouse.objects.filter(id=wh_id).first()
                if not wh and wh_code:
                    wh = Warehouse.objects.filter(code=wh_code).first()
                    if not wh:
                        wh = Warehouse.objects.create(code=wh_code, name=wh_code)
                if not wh:
                    raise ValueError("Kho không hợp lệ (cần warehouse_code hoặc warehouse_id).")

                # Validate lines
                if not isinstance(lines, list) or not lines:
                    raise ValueError("Thiếu lines.")

                skus = [str((ln.get("sku") or "").strip()) for ln in lines]
                qtys = []
                for ln in lines:
                    try:
                        q = int(ln.get("qty") or 0)
                    except Exception:
                        q = 0
                    qtys.append(q)
                if any((not s) for s in skus) or any(q <= 0 for q in qtys):
                    raise ValueError("Mỗi dòng cần sku và qty>0.")

                # Load/create products
                products = {p.sku: p for p in Product.objects.filter(sku__in=skus)}
                missing = [s for s in skus if s not in products]
                if missing:
                    for m in sorted(set(missing)):
                        if not m:
                            continue
                        p = Product.objects.create(sku=m, name=m)
                        products[p.sku] = p

                # Group by SKU
                grouped = defaultdict(int)
                for sku, qty in zip(skus, qtys):
                    grouped[sku] += int(qty)

                # Idempotent by external_id
                if external_id:
                    existing = StockOrder.objects.filter(external_id=external_id).first()
                    if existing:
                        results.append({
                            "external_id": external_id,
                            "order_id": existing.id,
                            "status": "skipped",
                        })
                        continue

                # Create order
                with transaction.atomic():
                    order = StockOrder.objects.create(
                        order_type=order_type,
                        source="API",
                        reference=reference,
                        external_id=external_id,
                        note=note,
                        from_wh=wh if order_type == "OUT" else None,
                        to_wh=wh if order_type == "IN" else None,
                    )
                    for sku, total_qty in grouped.items():
                        StockOrderLine.objects.create(
                            order=order,
                            product=products[sku],
                            quantity=total_qty,
                            note=note,
                        )
                    order.confirm(batch_id=f"API-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}")

                results.append({
                    "external_id": external_id,
                    "order_id": order.id,
                    "status": "created",
                })
            except Exception as e:
                results.append({
                    "external_id": od.get("external_id"),
                    "error": str(e),
                    "status": "error",
                })

        return Response({"results": results})


class InventoryView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        wh = request.GET.get("wh") or ""
        q = (request.GET.get("q") or "").strip()

        page = int(request.GET.get("page", 1))   # mặc định trang 1
        page_size = int(request.GET.get("page_size", 10))  # mặc định 10

        inv_qs = Inventory.objects.select_related("warehouse", "product")

        if wh:
            inv_qs = inv_qs.filter(warehouse_id=wh)

        if q:
            inv_qs = inv_qs.filter(
                Q(product__sku__icontains=q) |
                Q(product__name__icontains=q)
            )

        rows = (
            inv_qs.values("warehouse__code", "product__sku", "product__name")
            .annotate(qty=Sum("qty"))
            .order_by("warehouse__code", "product__sku")
        )

        total_records = rows.count()
        total_skus = inv_qs.values("product__sku").distinct().count()
        total_qty = sum(r["qty"] or 0 for r in rows)

        # pagination slice
        start = (page - 1) * page_size
        end = start + page_size
        paginated_rows = rows[start:end]

        return Response({
            "results": list(paginated_rows),
            "total_records": total_records,
            "total_skus": total_skus,
            "total_qty": total_qty,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_records + page_size - 1) // page_size,  # làm tròn lên
        })
# ---------- History (ITEM + BULK) ----------
class HistoryView(APIView):
    permission_classes = [AllowAny]

    def get_queryset(self, request):
        q = (request.GET.get("q") or "").strip()
        action = (request.GET.get("action") or "").strip().upper()
        wh_id = request.GET.get("wh") or ""
        start_s = request.GET.get("start") or ""
        end_s = request.GET.get("end") or ""

        def parse_date(s):
            try: return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception: return None

        start_d = parse_date(start_s)
        end_d = parse_date(end_s)

        qs = Move.objects.select_related("item__product","product","from_wh","to_wh")

        if start_d:
            qs = qs.filter(created_at__date__gte=start_d)
        if end_d:
            qs = qs.filter(created_at__date__lte=end_d)
        if action in {"IN","OUT"}:
            qs = qs.filter(action=action)
        if wh_id:
            if action == "IN":
                qs = qs.filter(to_wh_id=wh_id)
            elif action == "OUT":
                qs = qs.filter(from_wh_id=wh_id)
            else:
                qs = qs.filter(Q(from_wh_id=wh_id)|Q(to_wh_id=wh_id))
        if q:
            qs = qs.filter(
                Q(item__barcode_text__icontains=q)|
                Q(item__product__sku__icontains=q)|
                Q(item__product__name__icontains=q)|
                Q(item__product__code4__icontains=q)|
                Q(product__sku__icontains=q)|
                Q(product__name__icontains=q)|
                Q(batch_id__icontains=q)|
                Q(note__icontains=q)|
                Q(type_action__icontains=q)
            )
        return qs

    def get(self, request):
        qs = self.get_queryset(request)

        if (request.GET.get("export") or "").lower() == "csv":
            return export_history_csv(qs)

        # annotate unified fields
        qs = qs.annotate(
            u_kind=Case(
                When(item__isnull=False, then=Value("ITEM")),
                default=Value("BULK"),
                output_field=CharField(),
            ),
            u_barcode=F("item__barcode_text"),
            u_sku=Case(
                When(item__id__isnull=False, then=F("item__product__sku")),
                default=F("product__sku"),
                output_field=CharField(),
            ),
        )

        # ===== Summary counts =====
        summary = qs.aggregate(
            total_records=Count("id"),
            qty_in=Sum(
                Case(
                    When(action="IN", item__isnull=False, then=Value(1)),
                    When(action="IN", item__isnull=True, then=F("quantity")),
                    output_field=IntegerField(),
                )
            ),
            qty_out=Sum(
                Case(
                    When(action="OUT", item__isnull=False, then=Value(1)),
                    When(action="OUT", item__isnull=True, then=F("quantity")),
                    output_field=IntegerField(),
                )
            ),
        )

        # simple list, paging client-side
        data = MoveSerializer(qs.order_by("-created_at")[:1000], many=True).data

        return Response({
            "count": qs.count(),
            "total_records": summary["total_records"] or 0,
            "qty_in": summary["qty_in"] or 0,
            "qty_out": summary["qty_out"] or 0,
            "results": data
        })
# ---------- Real-time stats ----------
class HistoryStatsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        today = timezone.now().date()
        hour_ago = timezone.now() - timedelta(hours=1)
        stats = {
            "today_total": Move.objects.filter(created_at__date=today).count(),
            "today_in": Move.objects.filter(created_at__date=today, action="IN").count(),
            "today_out": Move.objects.filter(created_at__date=today, action="OUT").count(),
            "active_items": Item.objects.filter(status="in_stock").count(),
            "total_warehouses": Warehouse.objects.count(),
            "last_hour": Move.objects.filter(created_at__gte=hour_ago).count(),
            "last_update": timezone.now().isoformat(),
        }
        return Response(stats)

class HistoryUpdatesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        last_update = request.GET.get("last_update")
        if not last_update:
            return Response({"error":"Invalid timestamp"}, status=400)
        try:
            dt = datetime.fromisoformat(last_update.replace("Z","+00:00"))
        except ValueError:
            return Response({"error":"Invalid timestamp"}, status=400)
        new_moves = Move.objects.filter(created_at__gt=dt)
        return Response({
            "new_count": new_moves.count(),
            "latest_timestamp": timezone.now().isoformat(),
            "has_updates": new_moves.exists()
        })

# ---------- Manual Batch (session-based API) ----------
class ManualBatchView(APIView):
    """
    API dùng session (cookie) cho đơn thủ công:
    - POST /api/manual/start {action: IN|OUT, wh_id, allow_consume_itemized: bool}
    - GET  /api/manual/preview
    - POST /api/manual/lines {sku, qty}
    - DELETE /api/manual/lines/{idx}
    - POST /api/manual/clear
    - POST /api/manual/finalize
    - POST /api/manual/upload (multipart: file; flags: merge_duplicate, replace)
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, *args, **kwargs):
        path = request.path
        if path.endswith("/start"):
            action = (request.data.get("action") or "OUT").upper()
            wh_id = request.data.get("wh_id")
            allow = bool(request.data.get("allow_consume_itemized", False))
            wh = Warehouse.objects.filter(id=wh_id).first()
            if action not in ("IN","OUT") or not wh:
                return Response({"detail":"Action/Kho không hợp lệ."}, status=400)
            st = {
                "active": True,
                "action": action,
                "wh_id": wh.id,
                "allow_consume_itemized": allow,
                "lines": [],
                "batch_code": timezone.localtime().strftime("%Y%m%d-%H%M%S"),
            }
            _save_manual_batch(request, st)
            return Response({"detail":"OK","batch":st})

        if path.endswith("/lines"):
            st = _manual_batch(request)
            if not st.get("active"): return Response({"detail":"Chưa bắt đầu."}, status=400)
            sku = (request.data.get("sku") or "").strip()
            qty = int(request.data.get("qty") or 0)
            if not sku or qty <= 0: return Response({"detail":"SKU/Qty không hợp lệ."}, status=400)
            if not Product.objects.filter(sku=sku).exists():
                return Response({"detail":f"SKU {sku} không tồn tại."}, status=404)
            st["lines"].append({"sku": sku, "qty": qty})
            _save_manual_batch(request, st)
            return Response({"detail":"Đã thêm.", "lines": st["lines"]})

        if path.endswith("/clear"):
            st = _manual_batch(request); st["lines"]=[]; _save_manual_batch(request, st)
            return Response({"detail":"Đã xoá tất cả dòng."})

        if path.endswith("/finalize"):
            # Stateless finalize: read all inputs from request body instead of session
            def to_bool(v):
                s = str(v).strip().lower()
                return s in {"1","true","yes","on"}

            action = (request.data.get("action") or "").strip().upper()
            if action not in {"IN","OUT"}:
                return Response({"detail":"Thiếu hoặc action không hợp lệ (IN/OUT)."}, status=400)

            wh_id = request.data.get("wh_id")
            wh = Warehouse.objects.select_for_update().filter(id=wh_id).first()
            if not wh:
                return Response({"detail":"Kho không hợp lệ."}, status=400)

            allow = to_bool(request.data.get("allow_consume_itemized", False))

            batch_id = (request.data.get("batch_code") or "").strip() or timezone.localtime().strftime("%Y%m%d-%H%M%S")
            lines = request.data.get("lines") or []
            if not isinstance(lines, list) or not lines:
                return Response({"detail":"Thiếu lines."}, status=400)

            created_moves = 0
            with transaction.atomic():
                for ln in lines:
                    sku = (ln.get("sku") or "").strip()
                    try:
                        qty = int(ln.get("qty") or 0)
                    except (TypeError, ValueError):
                        return Response({"detail": f"Qty không hợp lệ cho SKU {sku}."}, status=400)
                    if not sku or qty <= 0:
                        return Response({"detail": f"Dòng không hợp lệ (sku/qty)."}, status=400)

                    product = Product.objects.filter(sku=sku).first()
                    if not product:
                        return Response({"detail": f"SKU {sku} không tồn tại."}, status=404)

                    if action == "IN":
                        Move.objects.create(product=product, quantity=qty, action="IN", to_wh=wh,
                                            type_action="MANUAL", note="IN (manual bulk)", batch_id=batch_id)
                        adjust_inventory(product, wh, +qty)
                        created_moves += 1
                    else:
                        bulk_used, picked_items = allocate_bulk_out(product, wh, qty, allow_consume_itemized=allow)
                        if bulk_used > 0:
                            Move.objects.create(product=product, quantity=bulk_used, action="OUT", from_wh=wh,
                                                type_action="MANUAL", note="OUT (manual bulk)", batch_id=batch_id)
                            adjust_inventory(product, wh, -bulk_used)
                            created_moves += 1
                        for it in picked_items:
                            Move.objects.create(item=it, action="OUT", from_wh=wh,
                                                type_action="MANUAL", note="OUT (manual picked)", batch_id=batch_id)
                            adjust_inventory(it.product, wh, -1)
                            it.warehouse = None; it.status = "shipped"; it.save(update_fields=["warehouse","status"])
                            created_moves += 1

            # Clear any session batch (optional)
            try:
                request.session["manual_batch"] = {"active": False, "lines": []}
                request.session.modified = True
            except Exception:
                pass

            return Response({"detail":"OK","batch_id":batch_id,"created_moves":created_moves})

        if path.endswith("/upload"):
            st = _manual_batch(request)
            if not st.get("active"): return Response({"detail":"Chưa bắt đầu."}, status=400)
            dj_file = request.FILES.get("file")
            if not dj_file: return Response({"detail":"Thiếu file."}, status=400)
            merge = str(request.data.get("merge_duplicate","")).lower() in {"1","true","yes"}
            replace = str(request.data.get("replace","")).lower() in {"1","true","yes"}
            try:
                rows = _parse_manual_file(dj_file)
                if merge: rows = _merge_lines(rows)
                new_lines = [{"sku": r["sku"], "qty": int(r["qty"])} for r in rows]
                if replace: st["lines"]=new_lines
                else: st["lines"].extend(new_lines)
                _save_manual_batch(request, st)
                total = sum(int(x["qty"]) for x in new_lines)
                return Response({"detail":"OK","added_lines":len(new_lines),"total_qty":total,"lines":st["lines"]})
            except Exception as e:
                return Response({"detail":f"Lỗi đọc file: {e}"}, status=400)

        # nếu path không match
        return Response({"detail":"Unsupported"}, status=404)

    def get(self, request, *args, **kwargs):
        path = request.path
        if path.endswith("/preview"):
            st = _manual_batch(request)
            if not st.get("active"): return Response({"detail":"Chưa bắt đầu."}, status=400)
            wh = Warehouse.objects.filter(id=st["wh_id"]).first()
            action = st["action"]
            allow = st.get("allow_consume_itemized", False)
            preview_rows=[]; total_warn=0
            for i,ln in enumerate(st.get("lines",[])):
                product = Product.objects.filter(sku=ln["sku"]).first()
                qty = int(ln["qty"])
                row={"idx":i,"sku":ln["sku"],"qty":qty,"valid": bool(product)}
                if product and action == "OUT":
                    pv = preview_bulk_out(product, wh, qty); row.update(pv)
                    row["status"]="OK" if pv["lack"]==0 else ("THIẾU (sẽ bốc item)" if allow else "THIẾU (bị chặn)")
                    if pv["lack"]>0 and not allow: total_warn+=1
                preview_rows.append(row)
            return Response({
                "batch": st, "warehouse": WarehouseSerializer(wh).data if wh else None,
                "preview_rows": preview_rows, "has_blocking": (total_warn>0) if action=="OUT" else False
            })
        # GET /api/manual/lines?remove=idx
        if path.endswith("/lines"):
            if "remove" in request.GET:
                try:
                    idx=int(request.GET["remove"])
                    st=_manual_batch(request)
                    if 0<=idx<len(st.get("lines",[])):
                        st["lines"].pop(idx); _save_manual_batch(request, st)
                        return Response({"detail":"Đã xoá.","lines":st["lines"]})
                except Exception:
                    pass
                return Response({"detail":"Index không hợp lệ."}, status=400)
            # else trả về danh sách dòng
            return Response({"lines": _manual_batch(request).get("lines",[])})
        return Response({"detail":"Unsupported"}, status=404)

def _should_affect_inventory(data) -> bool:
    """Trả về False nếu client gửi no_inv=True."""
    return str(data.get("no_inv")).lower() not in {"true", "1", "yes"}


# ---------- Scan Session (session-based API) ----------
class ScanView(APIView):
    """
    - POST /api/scan/start {action, action_type, wh_id, tag?}
    - POST /api/scan/stop
    - POST /api/scan/scan {barcode}
    - GET  /api/scan/state
    """
    permission_classes = [AllowAny]

    def post(self, request):
        path = request.path
        if path.endswith("/start"):
            # Read all from body; do not rely on previous session vars
            act = (request.data.get("action") or "").strip().upper()
            if act not in {"IN", "OUT"}:
                return Response({"detail": "Thiếu hoặc action không hợp lệ (IN/OUT)."}, status=400)
            wh_id = request.data.get("wh_id")
            wh = Warehouse.objects.filter(id=wh_id).first()
            tag_max = _tag_max_today(act, wh) + 1 if wh else 1
            note_user = (request.data.get("note_user") or "").strip()

            try:
                tag = int(request.data.get("tag") or tag_max)
            except (TypeError, ValueError):
                return Response({"detail": "Tag không hợp lệ."}, status=400)
            tag = tag if 1<=tag<=tag_max else tag_max
            st = {
                "active": True,
                "action": act,
                "type_action": request.data.get("action_type") or "",
                "wh_id": wh.id if wh else None,
                "tag": tag,
                "note_user": note_user,
                "started_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                "scanned": [],
            }
            try:
                logger.info("SCAN start: action=%s type=%s wh_id=%s tag=%s", act, st.get("type_action"), wh_id, tag)
            except Exception:
                pass
            _save_scan_state(request, st)
            return Response({"detail":"OK","state":st})

        if path.endswith("/stop"):
            st = _scan_state(request)
            st["active"]=False
            _save_scan_state(request, st)
            try:
                logger.info("SCAN stop: wh_id=%s tag=%s", st.get("wh_id"), st.get("tag"))
            except Exception:
                pass
            return Response({"detail":"Stopped","state":st})

        if path.endswith("/scan"):
            # Stateless scan: read all params from request body; session only stores last scanned list
            st = _scan_state(request)
            code = (request.data.get("barcode") or "").strip()
            note_user = (request.data.get("note_user") or st.get("note_user") or "").strip()
            affect_inv = _should_affect_inventory(request.data)
            if not code:
                return Response({"detail": "Thiếu barcode."}, status=400)
            action = (request.data.get("action") or "").strip().upper()
            if action not in {"IN", "OUT"}:
                return Response({"detail": "Thiếu hoặc action không hợp lệ (IN/OUT)."}, status=400)
            type_action = (request.data.get("type_action") or "").strip()
            if not type_action:
                return Response({"detail": "Thiếu type_action."}, status=400)
            tag_value = request.data.get("tag")
            try:
                tag = int(tag_value) if tag_value is not None else 1
            except (TypeError, ValueError):
                return Response({"detail": "Tag không hợp lệ."}, status=400)
            wh_id = request.data.get("wh_id")
            wh = Warehouse.objects.filter(id=wh_id).first() if wh_id else None
            if action == "IN" and not wh:
                return Response({"detail": "IN cần wh_id."}, status=400)

            # --- Logging request context ---
            try:
                logger.info(
                    "SCAN request: code=%s action=%s type=%s tag=%s wh_id=%s session_active=%s",
                    code, action, (type_action or ""), tag, wh_id, bool(st and st.get("active"))
                )
            except Exception:
                pass
            try:
                item = Item.objects.select_for_update().select_related("product","warehouse").get(barcode_text=code)
            except Item.DoesNotExist:
                logger.info("SCAN not_found: code=%s", code)
                return Response({"detail":f"Không tìm thấy {code}"}, status=404)

            with transaction.atomic():
                if action=="IN":
                    if item.warehouse:
                        logger.info("SCAN IN blocked: code=%s already in %s", code, item.warehouse.code if item.warehouse else None)
                        return Response({"detail":f"{code} đang ở {item.warehouse.code}."}, status=400)
                    Move.objects.create(item=item, action="IN", to_wh=wh, type_action=type_action, tag=tag, note="IN (scan)", note_user=note_user)
                    item.warehouse=wh; item.status="in_stock"; item.save(update_fields=["warehouse","status"])
                    if affect_inv:
                        adjust_inventory(item.product, wh, +1)
                    msg=f"IN {code} → {wh.code}"
                    logger.info("SCAN IN ok: code=%s to_wh=%s tag=%s type=%s", code, wh.code if wh else None, tag, type_action)
                else:
                    if not item.warehouse:
                        logger.info("SCAN OUT blocked: code=%s already OUT", code)
                        return Response({"detail":f"{code} đã OUT trước đó."}, status=400)
                    base_wh = wh or item.warehouse
                    if wh and item.warehouse != wh:
                        logger.info("SCAN OUT blocked: code=%s in %s but session wh=%s", code, item.warehouse.code if item.warehouse else None, wh.code if wh else None)
                        return Response({"detail":f"{code} đang ở {item.warehouse.code}, khác kho phiên ({wh.code})."}, status=400)
                    Move.objects.create(item=item, action="OUT", from_wh=base_wh, type_action=type_action, tag=tag, note= "OUT (scan)", note_user=note_user)
                    adjust_inventory(item.product, base_wh, -1)
                    item.warehouse=None; item.status="shipped"; item.save(update_fields=["warehouse","status"])
                    msg=f"OUT {code}"
                    logger.info("SCAN OUT ok: code=%s from_wh=%s tag=%s type=%s", code, base_wh.code if base_wh else None, tag, type_action)
            st["scanned"] = [code] + st.get("scanned", [])[:19]; _save_scan_state(request, st)
            return Response({"detail":msg,"state":st})
        return Response({"detail":"Unsupported"}, status=404)

    def get(self, request):
        return Response(_scan_state(request))

# # ---------- Generate labels API ----------
# class GenerateLabelsView(APIView):
#     """
#     POST /api/generate/labels
#     body:
#     {
#         "lines": [{"sku":"...","name":"...","qty":10,"import_date":"dd/mm/yyyy"}, ...]
#     }
#     -> tạo items + zip trả về file
#     """
#     permission_classes = [AllowAny]
#     def post(self, request):
#         lines = request.data.get("lines") or []
#         if not isinstance(lines, list) or not lines:
#             return Response({"detail":"Thiếu lines."}, status=400)

#         batch_code = timezone.localtime().strftime("%Y%m%d-%H%M%S")
#         batch_dir = MEDIA_ROOT / "labels" / batch_code
#         batch_dir.mkdir(parents=True, exist_ok=True)

#         from .utils import save_code128_png
#         total_created = 0

#         with transaction.atomic():
#             for row in lines:
#                 sku = (row.get("sku") or "").strip()
#                 name = (row.get("name") or "").strip()
#                 qty = int(row.get("qty") or 0)
#                 imp = row.get("import_date") or ""
#                 if not sku or qty<=0: continue
#                 import_dt = datetime.strptime(imp, "%d/%m/%Y").date() if imp else None
#                 product,_ = Product.objects.get_or_create(sku=sku, defaults={"name": name})
#                 if name and product.name!=name:
#                     product.name=name; product.save(update_fields=["name"])
#                 sku_dir = batch_dir / sku; sku_dir.mkdir(exist_ok=True)
#                 for _ in range(qty):
#                     item = Item.objects.create(product=product, import_date=import_dt)
#                     save_code128_png(item.barcode_text, product.name, out_dir=str(sku_dir))
#                     total_created += 1

#         zip_file = batch_dir / f"{batch_code}.zip"
#         with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
#             for p in batch_dir.rglob("*.png"):
#                 zf.write(p, arcname=str(p.relative_to(batch_dir)))
#             zf.writestr("MANIFEST.txt",
#                         f"Batch: {batch_code}\nGenerated: {timezone.localtime():%Y-%m-%d %H:%M:%S}\nFiles: {total_created}\n")

#         return FileResponse(open(zip_file, "rb"), as_attachment=True, filename=f"{batch_code}.zip")
# ---------- Generate labels API ----------
class GenerateLabelsView(APIView):
    """
    POST /api/generate/labels
    body:
    {
        "lines": [{"sku":"...","name":"...","qty":10,"import_date":"dd/mm/yyyy"}, ...]
    }
    -> tạo items + zip trả về file
    """
    permission_classes = [AllowAny]

    # helper: thay "/" thành Division Slash để an toàn tên file/thư mục
    @staticmethod
    def safe_filename(name: str) -> str:
        return (name or "").replace("/", "∕")  # U+2215

    def post(self, request):
        lines = request.data.get("lines") or []
        if not isinstance(lines, list) or not lines:
            return Response({"detail":"Thiếu lines."}, status=400)

        batch_code = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        batch_dir = MEDIA_ROOT / "labels" / batch_code
        batch_dir.mkdir(parents=True, exist_ok=True)

        from .utils import save_code128_png
        total_created = 0

        with transaction.atomic():
            for row in lines:
                sku = (row.get("sku") or "").strip()
                name = (row.get("name") or "").strip()
                qty = int(row.get("qty") or 0)
                imp = row.get("import_date") or ""
                if not sku or qty <= 0:
                    continue

                import_dt = datetime.strptime(imp, "%d/%m/%Y").date() if imp else None

                # Lưu SKU gốc trong DB (không thay đổi)
                product, _ = Product.objects.get_or_create(sku=sku, defaults={"name": name})
                if name and product.name != name:
                    product.name = name
                    product.save(update_fields=["name"])

                # Chỉ khi tạo thư mục/filename mới cần "an toàn"
                safe_sku_dirname = self.safe_filename(sku)
                sku_dir = batch_dir / safe_sku_dirname
                sku_dir.mkdir(exist_ok=True)

                for _ in range(qty):
                    item = Item.objects.create(product=product, import_date=import_dt)
                    # Barcode payload (item.barcode_text) vẫn giữ ký tự "/" gốc.
                    # Hàm save_code128_png sẽ tự làm "an toàn" khi tạo tên file.
                    save_code128_png(item.barcode_text, product.name, out_dir=str(sku_dir))
                    total_created += 1

        zip_file = batch_dir / f"{batch_code}.zip"
        with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in batch_dir.rglob("*.png"):
                zf.write(p, arcname=str(p.relative_to(batch_dir)))
            zf.writestr(
                "MANIFEST.txt",
                f"Batch: {batch_code}\nGenerated: {timezone.localtime():%Y-%m-%d %H:%M:%S}\nFiles: {total_created}\n"
            )

        return FileResponse(open(zip_file, "rb"), as_attachment=True, filename=f"{batch_code}.zip")


# ---------- Barcode Check (REST) ----------
class BarcodeCheckView(APIView):
    permission_classes = [AllowAny]

    def _item_payload(self, item):
        return {
            "id": item.id,
            "barcode": item.barcode_text,
            "status": item.status,
            "import_date": item.import_date.isoformat() if item.import_date else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "product": {
                "id": item.product.id if item.product else None,
                "sku": item.product.sku if item.product else None,
                "name": item.product.name if item.product else None,
                "code4": item.product.code4 if item.product else None,
            } if item.product else None,
            "warehouse": {
                "id": item.warehouse.id,
                "code": item.warehouse.code,
                "name": getattr(item.warehouse, "name", None),
            } if item.warehouse else None,
        }

    def _move_payload(self, mv):
        return {
            "id": mv.id,
            "action": mv.action,
            "type_action": mv.type_action,
            "from_wh": mv.from_wh.code if mv.from_wh else None,
            "to_wh": mv.to_wh.code if mv.to_wh else None,
            "tag": mv.tag,
            "note": mv.note,
            "created_at": mv.created_at.isoformat() if mv.created_at else None,
        }

    def _find_barcode(self, request):
        # Accept from query (?barcode=) or JSON/form body {barcode:}
        code = (request.query_params.get("barcode")
                or request.data.get("barcode")
                or request.data.get("code")
                or "").strip()
        return code

    def get(self, request):
        code = self._find_barcode(request)
        if not code:
            return Response({"detail": "Thiếu barcode."}, status=400)
        try:
            item = Item.objects.select_related("product", "warehouse").get(barcode_text=code)
        except Item.DoesNotExist:
            return Response({"detail": f"Không tìm thấy {code}"}, status=404)

        moves = (
            item.moves.select_related("from_wh", "to_wh")
                .order_by("-created_at")
        )
        return Response({
            "item": self._item_payload(item),
            "moves": [self._move_payload(m) for m in moves]
        })

    def post(self, request):
        # Same behavior as GET but read barcode from body
        return self.get(request)
class BatchTagSuggestAPI(APIView):
    """
    POST /api/batches/tag-suggest
    Body JSON:
      { "action": "IN" | "OUT", "warehouse": "<tên hoặc code>", (optional) "date": "YYYY-MM-DD" }
    Trả về:
      { action, warehouse, date, count, next, tags:[1..count+1] }
    - Đếm theo ngày (created_at__date = date). Nếu không gửi date thì dùng hôm nay (localdate).
    - IN: lọc Move(to_wh=warehouse); OUT: lọc Move(from_wh=warehouse).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser_in = BatchTagSuggestInputSerializer(data=request.data)
        if not ser_in.is_valid():
            return Response(ser_in.errors, status=400)

        action = ser_in.validated_data["action"]
        wh_text = ser_in.validated_data["warehouse"].strip()
        day = ser_in.validated_data.get("date") or timezone.localdate()

        # Tìm kho theo code hoặc name (không phân biệt hoa thường)
        wh = Warehouse.objects.filter(Q(code__iexact=wh_text) | Q(name__iexact=wh_text)).first()
        if not wh:
            return Response({"detail": f"Không tìm thấy warehouse '{wh_text}'"}, status=404)

        # Đếm distinct tag theo action + kho + ngày
        if action == "IN":
            qs = Move.objects.filter(action="IN", to_wh=wh, created_at__date=day)
        else:
            qs = Move.objects.filter(action="OUT", from_wh=wh, created_at__date=day)

        total = qs.values("tag").distinct().count()
        next_tag = total + 1
        tags = list(range(1, next_tag + 1))

        payload = {
            "action": action,
            "warehouse": WarehouseSerializer(wh).data,
            "date": day,
            "count": total,
            "next": next_tag,
            "tags": tags,
        }
        return Response(BatchTagSuggestOutputSerializer(payload).data, status=200)

# ---------- Beginning-of-Month Stocktake (BOM) ----------
class BOMStocktakeView(APIView):
    """
    POST /api/stocktake/bom

    Đầu vào (chọn 1 trong 2):
    A) JSON:
       {
         # --- Cách mới (khuyến nghị) ---
         "dt": "2025-09-03T22:53:05+07:00",   # datetime ISO-8601 (khuyến nghị)
         "dry_run": true,                      # tuỳ chọn (mặc định false)
         "batch_code": "BOM-20250903-225305",  # tuỳ chọn, mặc định BOM-<YYYYMMDD-HHMMSS> theo dt
         "lines": [
            {"warehouse_code":"VN", "sku":"FEGPLSEYECRM", "counted_qty":120},
            {"warehouse_code":"US", "sku":"SKUTFM", "counted_qty":40}
         ]

         # --- Cách cũ (tương thích) ---
         # "month": "2025-09"
       }

    B) multipart/form-data (CSV):
       - file=stocktake.csv (các cột: warehouse_code, sku, counted_qty)
       - dt=ISO-8601 (khuyến nghị) hoặc month=YYYY-MM (cũ)
       - dry_run=1 (tùy chọn)
       - batch_code=BOM-YYYYMMDD-HHMMSS (tùy chọn)

    Hành vi:
    - Tính delta = counted - current.
    - dry_run: chỉ trả delta, KHÔNG ghi.
    - !dry_run: tạo Move ADJUST IN/OUT theo delta và mv.apply().
    - Tránh double-apply theo batch_code trùng (409).
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # -------- helpers --------
    def _read_lines_from_request(self, request):
        if isinstance(request.data, dict) and "lines" in request.data:
            return request.data.get("lines") or []

        f = request.FILES.get("file")
        if not f:
            return None
        try:
            text = f.read().decode("utf-8-sig")
            rdr = csv.DictReader(io.StringIO(text))
            rows = []
            for r in rdr:
                rows.append({
                    "warehouse_code": (r.get("warehouse_code") or "").strip(),
                    "sku": (r.get("sku") or "").strip(),
                    "counted_qty": int(r.get("counted_qty") or 0),
                })
            return rows
        except Exception as e:
            raise ValidationError(f"Lỗi đọc CSV: {e}")

    def _parse_datetime(self, request):
        """
        Ưu tiên đọc dt|datetime (ISO-8601). Nếu không có, vẫn chấp nhận month=YYYY-MM (cũ).
        Trả về (aware_datetime, month_str_for_display_or_None).
        """
        tz = timezone.get_current_timezone()
        dt_raw = (request.data.get("dt")
                  or request.data.get("datetime")
                  or "").strip()

        if dt_raw:
            try:
                # Python 3.11: fromisoformat hỗ trợ 'YYYY-MM-DD HH:MM:SS' và 'T'
                dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
                if timezone.is_naive(dt):
                    dt = tz.localize(dt)
                return dt, None
            except Exception:
                raise ValidationError("Trường 'dt' (datetime) không hợp lệ. Dùng ISO-8601, ví dụ 2025-09-03T22:53:05+07:00")

        # Backward-compat: month=YYYY-MM (cũ)
        month = (request.data.get("month") or "").strip()
        if month:
            if not re.match(r"^\d{4}-\d{2}$", month):
                raise ValidationError("Trường 'month' không hợp lệ (YYYY-MM).")
            # Nếu chỉ có month, gán thời điểm là ngày 01 00:00 theo TZ hiện tại
            y, m = month.split("-")
            dt = tz.localize(datetime(int(y), int(m), 1, 0, 0, 0))
            return dt, month

        # Không có dt cũng không có month -> dùng now()
        return timezone.now(), None

    # -------- main --------
    def post(self, request):
        # --- thời điểm batch ---
        dt, month_for_display = self._parse_datetime(request)
        at_str = dt.isoformat(timespec="seconds")
        # batch_code mặc định: BOM-YYYYMMDD-HHMMSS
        default_batch = f"BOM-{dt.strftime('%Y%m%d-%H%M%S')}"
        batch_code = (request.data.get("batch_code") or default_batch).strip()
        dry_run = str(request.data.get("dry_run") or "").lower() in {"1","true","yes","on"}

        # --- đọc dữ liệu ---
        lines = self._read_lines_from_request(request)
        if lines is None or not isinstance(lines, list) or not lines:
            return Response({"detail": "Thiếu dữ liệu kiểm kê (lines hoặc file)."}, status=400)

        # Gom theo (warehouse_code, sku) -> lấy counted cuối cùng
        grouped = {}
        for ln in lines:
            whc = (ln.get("warehouse_code") or "").strip()
            sku = (ln.get("sku") or "").strip()
            try:
                qty = int(ln.get("counted_qty") or 0)
            except Exception:
                qty = 0
            if not whc or not sku:
                continue
            grouped[(whc, sku)] = qty

        if not dry_run:
            exists = Move.objects.filter(batch_id=batch_code, type_action="ADJUST").exists()
            if exists:
                return Response(
                    {"detail": f"Batch '{batch_code}' đã tồn tại (ADJUST). Không thể áp lại."},
                    status=409
                )

        results = []
        created_in = created_out = 0

        # Chuẩn bị map kho, sản phẩm
        wh_codes = sorted({whc for (whc, _) in grouped.keys()})
        skus = sorted({s for (_, s) in grouped.keys()})

        with transaction.atomic():
            wh_map = {w.code: w for w in Warehouse.objects.filter(code__in=wh_codes)}
            for whc in wh_codes:
                if whc not in wh_map:
                    wh_map[whc] = Warehouse.objects.create(code=whc, name=whc)

            prod_map = {p.sku: p for p in Product.objects.filter(sku__in=skus)}
            for s in skus:
                if s not in prod_map:
                    prod_map[s] = Product.objects.create(sku=s, name=s)

            # Tính delta & (nếu cần) apply
            for (whc, sku), counted in grouped.items():
                wh = wh_map[whc]
                prod = prod_map[sku]

                current = (Inventory.objects
                           .filter(product=prod, warehouse=wh)
                           .aggregate(t=Sum("qty")).get("t")) or 0
                delta = int(counted) - int(current)

                row = {
                    "at": at_str,                        # NEW
                    "month": month_for_display,          # giữ cho tương thích (có thể None)
                    "batch_id": batch_code,
                    "warehouse": whc,
                    "sku": sku,
                    "current": current,
                    "counted": counted,
                    "delta": delta
                }

                if dry_run or delta == 0:
                    row["status"] = "no_change" if delta == 0 else "preview"
                    results.append(row)
                    continue

                note = f"BOM {at_str} adjust {('+' if delta>0 else '')}{delta}"

                if delta > 0:
                    mv = Move.objects.create(
                        product=prod, quantity=delta, action="IN",
                        to_wh=wh, type_action="ADJUST",
                        note=note, batch_id=batch_code
                    )
                    mv.apply()
                    created_in += 1
                    row["status"] = "IN"
                    row["move_id"] = mv.id
                else:
                    mv = Move.objects.create(
                        product=prod, quantity=abs(delta), action="OUT",
                        from_wh=wh, type_action="ADJUST",
                        note=note, batch_id=batch_code
                    )
                    mv.apply()
                    created_out += 1
                    row["status"] = "OUT"
                    row["move_id"] = mv.id

                results.append(row)

        payload = {
            "detail": "PREVIEW" if dry_run else "OK",
            "at": at_str,                    # NEW: thời điểm batch
            "batch_id": batch_code,
            "created_moves_in": created_in,
            "created_moves_out": created_out,
            "lines": results[:2000]
        }
        # vẫn trả kèm "month" nếu client cũ cần
        if month_for_display:
            payload["month"] = month_for_display

        return Response(payload, status=200 if dry_run else 201)


# ---------- Reprint Barcodes (REST) ----------
BARCODE_RE = re.compile(r"^\d{15}$")  # 4 + 6 + 5 theo quy ước

class ReprintBarcodesView(APIView):
    """
    POST /api/barcodes/reprint
    Body:
    {
        "lines": ["927610092500022", "...."],  # danh sách barcode cần in lại
        "out_dir": "labels/reprint"            # (optional) thư mục gốc chứa batch trong MEDIA_ROOT
    }

    Hành vi:
    - Không tạo Item mới.
    - Sinh ảnh PNG cho từng barcode trong 'lines', đặt trong batch: <out_dir>/<YYYYMMDD-HHMMSS>/
    - Đóng gói ZIP và trả về file đính kèm.
    """
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    @staticmethod
    def _sanitize_relpath(p: str) -> Path:
        """
        Làm sạch đường dẫn tương đối do user cung cấp:
        - Chuyển backslash -> slash
        - Loại bỏ các segment rỗng, '.', '..'
        - Chỉ cho phép [A-Za-z0-9._-] trong từng segment
        """
        p = (p or "").replace("\\", "/").strip().lstrip("/")  # bỏ leading slash
        parts = []
        for seg in p.split("/"):
            seg = seg.strip()
            if not seg or seg in {".", ".."}:
                continue
            # filter ký tự lạ để tránh lỗi FS và traversal lạ
            clean = re.sub(r"[^A-Za-z0-9._-]", "_", seg)
            if clean:
                parts.append(clean)
        return Path(*parts) if parts else Path("labels") / "reprint"

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        lines = data.get("lines") or []
        if not isinstance(lines, list) or not lines:
            return Response({"detail": "Thiếu 'lines' (list barcode)."}, status=400)

        # Loại trùng, giữ thứ tự
        seen = set()
        codes = []
        for raw in lines:
            s = str(raw).strip()
            if not s:
                continue
            if s not in seen:
                seen.add(s)
                codes.append(s)

        if not codes:
            return Response({"detail": "Không có barcode hợp lệ trong 'lines'."}, status=400)

        # Thư mục batch (an toàn)
        out_dir_rel_raw = (data.get("out_dir") or "").strip()
        out_dir_rel = self._sanitize_relpath(out_dir_rel_raw)
        ts = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        base_media = Path(settings.MEDIA_ROOT)  # ✅ dùng settings.MEDIA_ROOT
        batch_dir = base_media / out_dir_rel / ts
        batch_dir.mkdir(parents=True, exist_ok=True)

        # Sinh ảnh
        total_ok = 0
        errors = []

        for code in codes:
            if not BARCODE_RE.match(code):
                errors.append(f"INVALID_FORMAT: {code}")
                continue

            # Lấy title nếu có (tên sản phẩm) – không ảnh hưởng tên file (đã safe trong utils)
            title = ""
            try:
                it = Item.objects.select_related("product").filter(barcode_text=code).first()
                if it and it.product and it.product.name:
                    title = it.product.name
            except Exception as e:
                errors.append(f"LOOKUP_ERROR: {code}: {e}")

            try:
                save_code128_png(code, title=title, out_dir=str(batch_dir))
                total_ok += 1
            except Exception as e:
                errors.append(f"GEN_ERROR: {code}: {e}")

        if total_ok == 0:
            return Response({"detail": "Không in được ảnh nào.", "errors": errors}, status=400)

        # Đóng gói ZIP (trên đĩa)
        zip_path = batch_dir / f"reprint-{ts}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # add toàn bộ *.png trong batch_dir và subfolder
            for p in batch_dir.rglob("*.png"):
                zf.write(p, arcname=str(p.relative_to(batch_dir)))
            if errors:
                zf.writestr("errors.txt", "\n".join(errors))
            zf.writestr(
                "MANIFEST.txt",
                (
                    f"Reprint batch: {ts}\n"
                    f"Folder: {out_dir_rel.as_posix()}\n"
                    f"Files: {total_ok}\n"
                    f"Generated at: {timezone.localtime():%Y-%m-%d %H:%M:%S}\n"
                )
            )

        # Trả file
        return FileResponse(open(zip_path, "rb"), as_attachment=True, filename=zip_path.name)
