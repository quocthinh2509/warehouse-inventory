# inventory/api_views.py
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Sum, Max, Count, F, IntegerField, CharField, Case, When, Value
from django.db import transaction
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest
from django.conf import settings
from pathlib import Path
import csv, io, re, zipfile

from rest_framework import viewsets, mixins, status
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Product, Warehouse, Item, Inventory, Move
from .serializers import (
    ProductSerializer, WarehouseSerializer, ItemSerializer,
    InventorySerializer, MoveSerializer
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

# ---------- CRUD cơ bản ----------
class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.all().order_by("code")
    serializer_class = WarehouseSerializer
    permission_classes = [AllowAny]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("sku")
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(sku__icontains=q)|Q(name__icontains=q)|Q(code4__icontains=q))
        return qs

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
            st = _manual_batch(request)
            if not st.get("active"): return Response({"detail":"Chưa bắt đầu."}, status=400)
            with transaction.atomic():
                wh = Warehouse.objects.select_for_update().filter(id=st["wh_id"]).first()
                action = st["action"]
                allow = st.get("allow_consume_itemized", False)
                batch_id = st.get("batch_code") or timezone.localtime().strftime("%Y%m%d-%H%M%S")
                created_moves = 0
                for ln in st.get("lines", []):
                    product = Product.objects.filter(sku=ln["sku"]).first()
                    if not product: continue
                    qty = int(ln["qty"])
                    if action == "IN":
                        Move.objects.create(product=product, quantity=qty, action="IN", to_wh=wh,
                                            type_action="MANUAL", note="IN (manual bulk)", batch_id=batch_id)
                        adjust_inventory(product, wh, +qty)
                        created_moves += 1
                    else:
                        bulk_used, picked_items = allocate_bulk_out(product, wh, qty, allow_consume_itemized=allow)
                        if bulk_used>0:
                            Move.objects.create(product=product, quantity=bulk_used, action="OUT", from_wh=wh,
                                                type_action="MANUAL", note="OUT (manual bulk)", batch_id=batch_id)
                            adjust_inventory(product, wh, -bulk_used); created_moves += 1
                        for it in picked_items:
                            Move.objects.create(item=it, action="OUT", from_wh=wh,
                                                type_action="MANUAL", note="OUT (manual picked)", batch_id=batch_id)
                            adjust_inventory(it.product, wh, -1)
                            it.warehouse=None; it.status="shipped"; it.save(update_fields=["warehouse","status"])
                            created_moves += 1
                request.session["manual_batch"]={"active":False,"lines":[]}; request.session.modified=True
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
            act = (request.data.get("action") or "IN").upper()
            wh_id = request.data.get("wh_id")
            wh = Warehouse.objects.filter(id=wh_id).first()
            tag_max = _tag_max_today(act, wh) + 1 if wh else 1
            tag = int(request.data.get("tag") or tag_max)
            tag = tag if 1<=tag<=tag_max else tag_max
            st = {
                "active": True,
                "action": act,
                "type_action": request.data.get("action_type") or "",
                "wh_id": wh.id if wh else None,
                "tag": tag,
                "started_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                "scanned": [],
            }
            _save_scan_state(request, st)
            return Response({"detail":"OK","state":st})

        if path.endswith("/stop"):
            st = _scan_state(request); st["active"]=False; _save_scan_state(request, st)
            return Response({"detail":"Stopped","state":st})

        if path.endswith("/scan"):
            st=_scan_state(request)
            # if not st.get("active"): return Response({"detail":"Chưa bắt đầu."}, status=400)
            code=(request.data.get("barcode") or "").strip()
            if not code: return Response({"detail":"Thiếu barcode."}, status=400)
            action = (st.get("action") if st else request.data.get("action"))
            type_action = st.get("type_action") if st and st.get("type_action") else request.data.get("type_action")
            if not type_action:
                return Response({"detail": "Thiếu type_action."}, status=400)
            tag_value = st.get("tag") if st and st.get("tag") is not None else request.data.get("tag")
            tag = int(tag_value) if tag_value is not None else 1
            wh_id = (st.get("wh_id") if st else request.data.get("wh_id"))
            wh = Warehouse.objects.filter(id=st.get("wh_id")).first()
            try:
                item = Item.objects.select_for_update().select_related("product","warehouse").get(barcode_text=code)
            except Item.DoesNotExist:
                return Response({"detail":f"Không tìm thấy {code}"}, status=404)

            with transaction.atomic():
                if action=="IN":
                    if item.warehouse:
                        return Response({"detail":f"{code} đang ở {item.warehouse.code}."}, status=400)
                    Move.objects.create(item=item, action="IN", to_wh=wh, type_action=type_action, tag=tag, note="IN (scan)")
                    item.warehouse=wh; item.status="in_stock"; item.save(update_fields=["warehouse","status"])
                    adjust_inventory(item.product, wh, +1)
                    msg=f"IN {code} → {wh.code}"
                else:
                    if not item.warehouse:
                        return Response({"detail":f"{code} đã OUT trước đó."}, status=400)
                    base_wh = wh or item.warehouse
                    if wh and item.warehouse != wh:
                        return Response({"detail":f"{code} đang ở {item.warehouse.code}, khác kho phiên ({wh.code})."}, status=400)
                    Move.objects.create(item=item, action="OUT", from_wh=base_wh, type_action=type_action, tag=tag, note="OUT (scan)")
                    adjust_inventory(item.product, base_wh, -1)
                    item.warehouse=None; item.status="shipped"; item.save(update_fields=["warehouse","status"])
                    msg=f"OUT {code}"
            st["scanned"] = [code] + st.get("scanned", [])[:19]; _save_scan_state(request, st)
            return Response({"detail":msg,"state":st})
        return Response({"detail":"Unsupported"}, status=404)

    def get(self, request):
        return Response(_scan_state(request))

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
                if not sku or qty<=0: continue
                import_dt = datetime.strptime(imp, "%d/%m/%Y").date() if imp else None
                product,_ = Product.objects.get_or_create(sku=sku, defaults={"name": name})
                if name and product.name!=name:
                    product.name=name; product.save(update_fields=["name"])
                sku_dir = batch_dir / sku; sku_dir.mkdir(exist_ok=True)
                for _ in range(qty):
                    item = Item.objects.create(product=product, import_date=import_dt)
                    save_code128_png(item.barcode_text, product.name, out_dir=str(sku_dir))
                    total_created += 1

        zip_file = batch_dir / f"{batch_code}.zip"
        with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in batch_dir.rglob("*.png"):
                zf.write(p, arcname=str(p.relative_to(batch_dir)))
            zf.writestr("MANIFEST.txt",
                        f"Batch: {batch_code}\nGenerated: {timezone.localtime():%Y-%m-%d %H:%M:%S}\nFiles: {total_created}\n")

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
