from pathlib import Path
import re, io, zipfile
import csv

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, connection
from django.db.models import Q, Max, Count, Sum, F, Avg, Case, When, Value, IntegerField,  CharField
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.utils import timezone
from django.http import Http404, HttpResponse, HttpResponseBadRequest, FileResponse, JsonResponse
from django.urls import reverse
from urllib.parse import quote
from django.db.models.functions import Extract, TruncHour
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST, require_GET

from datetime import datetime, date, timedelta
from shutil import make_archive
from .models import Product, Warehouse, Item, Inventory, Move, SavedQuery
from .forms import GenerateForm, ScanMoveForm, ProductForm, SQLQueryForm
from .utils import make_payload, save_code128_png
from io import StringIO
MEDIA_ROOT = Path(settings.MEDIA_ROOT)

# ---------- Trang chính & Dashboard ----------
def index(request):
    # vào web -> generate
    return redirect("generate_labels")

def config_index(request):
    # Trang hub hiển thị 3 ô: Query Panel, Products, Admin
    return render(request, "inventory/config_index.html")

def dashboard_redirect(request):
    return redirect("dashboard_warehouse")


# -------- trang dashboard warehouse ---------

def dashboard_warehouse(request):
    wh_id = request.GET.get("wh") or ""
    q     = (request.GET.get("q") or "").strip()
    per   = int(request.GET.get("per") or 50)

    warehouses = Warehouse.objects.all().order_by("code")

    inv_qs = Inventory.objects.select_related("warehouse", "product")
    if wh_id:
        inv_qs = inv_qs.filter(warehouse_id=wh_id)
    if q:
        inv_qs = inv_qs.filter(Q(product__sku__icontains=q) | Q(product__name__icontains=q))

    rows = (
        inv_qs.values("warehouse__code", "product__sku", "product__name")
              .annotate(qty=Sum("qty"))
              .order_by("warehouse__code", "product__sku")
    )

    pager = Paginator(list(rows), per)
    page  = pager.get_page(request.GET.get("page", 1))

    # Thêm thống kê hôm nay
    today = timezone.now().date()
    
    # Base queryset cho Move hôm nay
    move_today_qs = Move.objects.filter(
        created_at__date=today
    )
    
    # Nếu có filter warehouse, áp dụng cho move
    if wh_id:
        move_today_qs = move_today_qs.filter(
            Q(from_wh_id=wh_id) | Q(to_wh_id=wh_id)
        )
    
    # Tính tổng IN và OUT hôm nay (đếm số lượng items, mỗi move = 1 item)
    today_in = move_today_qs.filter(action='IN').count()
    today_out = move_today_qs.filter(action='OUT').count()

    return render(request, "inventory/dashboard_warehouse.html", {
        "active_tab": "warehouse",
        "warehouses": warehouses,
        "wh_id": str(wh_id),
        "q": q,
        "per": per,
        "per_options": [25, 50, 100, 200],
        "page": page,
        "total_skus": rows.values("product__sku").distinct().count(),
        "total_qty": sum(r["qty"] or 0 for r in rows),
        "today_in": today_in,
        "today_out": today_out,
    })

# ---- Tab 2: Barcodes (liệt kê barcode)

def dashboard_barcodes(request):
    # Lấy tham số filter
    q = (request.GET.get('q') or '').strip()
    wh = request.GET.get('wh') or ''
    status = request.GET.get('status') or ''
    date_from = request.GET.get('date_from') or ''
    date_to = request.GET.get('date_to') or ''
    per = int(request.GET.get('per') or 50)

    # Base queryset
    items_qs = Item.objects.select_related('product', 'warehouse').order_by('-created_at')

    # Apply filters
    if q:
        items_qs = items_qs.filter(
            Q(barcode_text__icontains=q) |
            Q(product__sku__icontains=q) |
            Q(product__name__icontains=q) |
            Q(product__code4__icontains=q)
        )
    if wh:
        items_qs = items_qs.filter(warehouse_id=wh)
    if status:
        items_qs = items_qs.filter(status=status)
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            items_qs = items_qs.filter(created_at__date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            items_qs = items_qs.filter(created_at__date__lte=date_to_parsed)
        except ValueError:
            pass

    # === Export CSV ===
    if (request.GET.get('export') or '').lower() == 'csv':
        return export_barcodes_csv(items_qs)

    # Statistics
    today = timezone.now().date()
    all_items = Item.objects.all()
    total_items = all_items.count()
    in_stock_count = all_items.filter(status='in_stock').count()
    shipped_count = all_items.filter(status='shipped').count()
    today_created = all_items.filter(created_at__date=today).count()
    unique_products = all_items.values('product').distinct().count()
    active_warehouses = all_items.exclude(warehouse__isnull=True).values('warehouse').distinct().count()

    # Pagination
    paginator = Paginator(items_qs, per)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)

    # Warehouses cho dropdown
    warehouses = Warehouse.objects.all().order_by('code')

    context = {
        'active_tab': 'barcodes',
        'page': page,
        'warehouses': warehouses,
        'q': q,
        'wh': wh,
        'status': status,
        'date_from': date_from,
        'date_to': date_to,
        'per': per,
        'per_options': [25, 50, 100, 200, 500],

        # Statistics
        'total_items': total_items,
        'in_stock_count': in_stock_count,
        'shipped_count': shipped_count,
        'today_created': today_created,
        'unique_products': unique_products,
        'active_warehouses': active_warehouses,
    }
    return render(request, 'inventory/dashboard_barcodes.html', context)


def export_barcodes_csv(queryset):
    """Xuất CSV danh sách barcode theo bộ lọc hiện tại."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="barcodes.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'barcode', 'sku', 'product_name', 'warehouse', 'status',
        'created_at', 'import_date'
    ])

    for it in queryset.iterator(chunk_size=1000):
        writer.writerow([
            it.barcode_text,
            it.product.sku if it.product else '',
            it.product.name if it.product else '',
            it.warehouse.code if it.warehouse else '',
            it.status or '',
            timezone.localtime(it.created_at).strftime('%Y-%m-%d %H:%M:%S') if it.created_at else '',
            it.import_date.strftime('%Y-%m-%d') if it.import_date else '',
        ])
    return response


# ---- Tab 3: History (đổi tên từ dashboard cũ của bạn)

def dashboard_history(request):
    """Enhanced dashboard history: show both ITEM & BULK in one table"""
    # Get filter parameters
    q = (request.GET.get("q") or "").strip()
    action = (request.GET.get("action") or "").strip().upper()
    wh_id = request.GET.get("wh") or ""
    start_s = request.GET.get("start") or ""
    end_s = request.GET.get("end") or ""

    # Sorting & page size
    sort = request.GET.get("sort") or "created_at"
    dir_ = (request.GET.get("dir") or "desc").lower()
    per = request.GET.get("per") or "200"
    try:
        per = max(1, min(int(per), 2000))
    except Exception:
        per = 200

    # Date parse
    def parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    start_d = parse_date(start_s)
    end_d = parse_date(end_s)

    # Quick date ranges
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Base queryset (chú ý: có cả bulk product)
    qs = (
        Move.objects.select_related("item__product", "product", "from_wh", "to_wh")
        .prefetch_related("item__product")
    )

    # Filters
    if start_d:
        qs = qs.filter(created_at__date__gte=start_d)
    if end_d:
        qs = qs.filter(created_at__date__lte=end_d)
    if action in {"IN", "OUT"}:
        qs = qs.filter(action=action)
    if wh_id:
        if action == "IN":
            qs = qs.filter(to_wh_id=wh_id)
        elif action == "OUT":
            qs = qs.filter(from_wh_id=wh_id)
        else:
            qs = qs.filter(Q(from_wh_id=wh_id) | Q(to_wh_id=wh_id))
    if q:
        qs = qs.filter(
            Q(item__barcode_text__icontains=q) |
            Q(item__product__sku__icontains=q) |
            Q(item__product__name__icontains=q) |
            Q(item__product__code4__icontains=q) |
            Q(product__sku__icontains=q) |           # BULK
            Q(product__name__icontains=q) |          # BULK
            Q(batch_id__icontains=q) |
            Q(note__icontains=q) |
            Q(type_action__icontains=q)
        )

    # CSV early exit
    if (request.GET.get("export") or "").lower() == "csv":
        return export_history_csv(qs)

    # Annotate unified fields
    qs = qs.annotate(
        u_kind=Case(
            When(item__isnull=False, then=Value("ITEM")),
            default=Value("BULK"),
            output_field=CharField(),
        ),
        u_barcode=F("item__barcode_text"),
        u_sku=Coalesce(F("item__product__sku"), F("product__sku")),
        u_name=Coalesce(F("item__product__name"), F("product__name")),
        u_qty=Case(
            When(product__isnull=False, then=F("quantity")),  # BULK
            default=Value(1),                                 # ITEM
            output_field=IntegerField(),
        ),
    )

    # Sorting
    sort_map = {
        "created_at": "created_at",
        "u_kind": "u_kind",
        "u_barcode": "u_barcode",
        "u_sku": "u_sku",
        "u_name": "u_name",
        "u_qty": "u_qty",
        "action": "action",
        "from_wh": "from_wh__code",
        "to_wh": "to_wh__code",
        "type_action": "type_action",
        "note": "note",
        "tag": "tag",
        "batch_id": "batch_id",
        # backward-compat keys from old template:
        "barcode": "u_barcode",
        "sku": "u_sku",
    }
    sort_field = sort_map.get(sort, "created_at")
    if dir_ != "asc":
        sort_field = "-" + sort_field
    qs = qs.order_by(sort_field)

    # Fetch rows
    logs = list(qs[:per])
    total_rows = qs.count()

    # ==== Analytics (tính theo QTY) ====
    def base_filtered():
        bq = Move.objects.select_related("product")
        if start_d:
            bq = bq.filter(created_at__date__gte=start_d)
        if end_d:
            bq = bq.filter(created_at__date__lte=end_d)
        if wh_id:
            bq = bq.filter(Q(from_wh_id=wh_id) | Q(to_wh_id=wh_id))
        if q:
            bq = bq.filter(
                Q(item__barcode_text__icontains=q) |
                Q(item__product__sku__icontains=q) |
                Q(item__product__name__icontains=q) |
                Q(item__product__code4__icontains=q) |
                Q(product__sku__icontains=q) |
                Q(product__name__icontains=q) |
                Q(batch_id__icontains=q) |
                Q(note__icontains=q) |
                Q(type_action__icontains=q)
            )
        return bq

    base_qs = base_filtered().annotate(
        u_qty=Case(
            When(product__isnull=False, then=F("quantity")),
            default=Value(1),
            output_field=IntegerField(),
        )
    )
    total_in_qty = base_qs.filter(action="IN").aggregate(s=Sum("u_qty"))["s"] or 0
    total_out_qty = base_qs.filter(action="OUT").aggregate(s=Sum("u_qty"))["s"] or 0

    analytics = calculate_advanced_analytics(base_qs, start_d, end_d)

    warehouses = Warehouse.objects.all().order_by("code")

    context = {
        "active_tab": "history",
        "logs": logs,
        "total_rows": total_rows,
        "total_in_qty": total_in_qty,
        "total_out_qty": total_out_qty,
        "q": q,
        "action": action,
        "wh_id": str(wh_id),
        "start": start_s,
        "end": end_s,
        "sort": request.GET.get("sort") or "created_at",
        "dir": dir_,
        "per": per,
        "warehouses": warehouses,
        "per_options": [100, 200, 500, 1000, 2000],
        # Quick date filters
        "today": today.strftime("%Y-%m-%d"),
        "yesterday": yesterday.strftime("%Y-%m-%d"),
        "week_start": week_start.strftime("%Y-%m-%d"),
        "month_start": month_start.strftime("%Y-%m-%d"),
        # analytics (giữ nguyên keys cũ nếu bạn đang dùng)
        **analytics,
    }
    return render(request, "inventory/dashboard_history.html", context)


def calculate_advanced_analytics(base_qs, start_d, end_d):
    """Calculate advanced analytics for the dashboard"""
    
    # Most active warehouse
    most_active_wh = (
        base_qs.values("from_wh__code", "to_wh__code")
        .annotate(
            warehouse=F("from_wh__code"),
            count=Count("id")
        )
        .exclude(warehouse__isnull=True)
        .order_by("-count")
        .first()
    )
    
    if not most_active_wh:
        most_active_wh = (
            base_qs.values("to_wh__code")
            .annotate(
                warehouse=F("to_wh__code"),
                count=Count("id")
            )
            .exclude(warehouse__isnull=True)
            .order_by("-count")
            .first()
        )
    
    # Daily average calculation
    daily_avg = 0
    if start_d and end_d:
        days_diff = (end_d - start_d).days + 1
        if days_diff > 0:
            daily_avg = base_qs.count() / days_diff
    
    # Peak hour analysis (for today only)
    today = timezone.now().date()
    peak_hour = None
    peak_hour_count = 0
    
    today_moves = base_qs.filter(created_at__date=today)
    if today_moves.exists():
        hourly_stats = (
            today_moves.annotate(hour=Extract('created_at', 'hour'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )
        
        if hourly_stats:
            peak_hour = f"{hourly_stats['hour']:02d}:00"
            peak_hour_count = hourly_stats['count']
    
    # Transaction type distribution
    type_distribution = (
        base_qs.values('type_action')
        .annotate(count=Count('id'))
        .exclude(type_action='')
        .order_by('-count')[:5]  # Top 5 transaction types
    )
    
    # Recent activity trends (last 7 days)
    week_ago = timezone.now().date() - timedelta(days=7)
    recent_trends = []
    
    for i in range(7):
        day = week_ago + timedelta(days=i)
        day_count = base_qs.filter(created_at__date=day).count()
        recent_trends.append({
            'date': day,
            'count': day_count,
            'day_name': day.strftime('%a')
        })
    
    return {
        'most_active_wh': {
            'code': most_active_wh['warehouse'] if most_active_wh else 'N/A',
            'count': most_active_wh['count'] if most_active_wh else 0
        },
        'daily_avg': daily_avg,
        'peak_hour': peak_hour,
        'peak_hour_count': peak_hour_count,
        'type_distribution': list(type_distribution),
        'recent_trends': recent_trends,
    }


def export_history_csv(queryset):
    """Optimized CSV export for transaction history"""
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="transaction_history.csv"'
    
    writer = csv.writer(response)
    
    # Enhanced CSV headers
    headers = [
        'timestamp','date','time',
        'barcode','sku','product_name','product_code4',
        'bulk_sku','bulk_qty',               # ✨ thêm
        'action','from_warehouse','to_warehouse',
        'transaction_type','note','tag','batch_id','day_of_week','hour'
    ]
    writer.writerow(headers)
    
    # Stream the data to handle large datasets efficiently
    for move in queryset.iterator(chunk_size=1000):
        local_time = timezone.localtime(move.created_at)
        item = getattr(move, "item", None)
        prod = item.product if item else None
        bulk_prod = getattr(move, "product", None)
        writer.writerow([
            local_time.strftime('%Y-%m-%d %H:%M:%S'),
            local_time.strftime('%Y-%m-%d'),
            local_time.strftime('%H:%M:%S'),
            item.barcode_text if item else '',
            prod.sku if prod else '',
            prod.name if prod else '',
            prod.code4 if prod else '',
            bulk_prod.sku if bulk_prod else '',              # ✨
            move.quantity if bulk_prod else '',              # ✨
            move.action,
            move.from_wh.code if move.from_wh else '',
            move.to_wh.code if move.to_wh else '',
            move.type_action or '',
            move.note or '',
            move.tag,
            move.batch_id or '',                             # ✨
            local_time.strftime('%A'),
            local_time.hour,
        ])
    
    return response


def dashboard_history_api(request):
    """API endpoint for real-time updates"""
    
    # Get the last known timestamp
    last_update = request.GET.get('last_update')
    if last_update:
        try:
            last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            new_moves = Move.objects.filter(
                created_at__gt=last_update_dt
            ).select_related('item__product', 'from_wh', 'to_wh')
            
            # Return count and latest timestamp
            data = {
                'new_count': new_moves.count(),
                'latest_timestamp': timezone.now().isoformat(),
                'has_updates': new_moves.exists()
            }
            
            return JsonResponse(data)
        except ValueError:
            pass
    
    return JsonResponse({'error': 'Invalid timestamp'}, status=400)


def dashboard_history_stats(request):
    """API endpoint for dashboard statistics"""
    
    today = timezone.now().date()
    
    # Real-time statistics
    stats = {
        'today_total': Move.objects.filter(created_at__date=today).count(),
        'today_in': Move.objects.filter(created_at__date=today, action='IN').count(),
        'today_out': Move.objects.filter(created_at__date=today, action='OUT').count(),
        'active_items': Item.objects.filter(status='in_stock').count(),
        'total_warehouses': Warehouse.objects.count(),
        'last_update': timezone.now().isoformat(),
    }
    
    # Recent activity (last hour)
    hour_ago = timezone.now() - timedelta(hours=1)
    stats['last_hour'] = Move.objects.filter(
        created_at__gte=hour_ago
    ).count()
    
    return JsonResponse(stats)

# ---------- Helper tồn kho ----------
def adjust_inventory(product: Product, warehouse: Warehouse, delta: int):
    """Điều chỉnh tồn kho, không cho âm."""
    inv, _ = Inventory.objects.get_or_create(
        product=product, warehouse=warehouse, defaults={"qty": 0}
    )
    inv.qty = max(0, inv.qty + delta)
    inv.save(update_fields=["qty"])

def _get_queue(request):
    return request.session.setdefault("gen_queue", [])

def _save_queue(request, q):
    request.session["gen_queue"] = q
    request.session.modified = True

# ==== Manual batch in session ====

def _manual_batch(request):
    """
    Cấu trúc:
    {
      "active": True, "action": "OUT"|"IN", "wh_id": 1,
      "allow_consume_itemized": False,
      "lines": [{"sku": "...", "qty": 5}, ...],
      "batch_code": "20250828-103000"
    }
    """
    return request.session.setdefault("manual_batch", {"active": False, "lines": []})

def _save_manual_batch(request, st):
    request.session["manual_batch"] = st
    request.session.modified = True


def get_itemized_count(product: Product, warehouse: Warehouse) -> int:
    # số Item có barcode đang in_stock ở kho
    return Item.objects.filter(product=product, warehouse=warehouse, status="in_stock").count()

def get_pools_locked(product: Product, warehouse: Warehouse):
    """
    Lấy tồn kho + tách pool bulk vs itemized. Gọi trong transaction.
    bulk_pool = Inventory.qty - itemized_count
    """
    inv = Inventory.objects.select_for_update().get(product=product, warehouse=warehouse)
    itemized_cnt = get_itemized_count(product, warehouse)
    bulk_pool = inv.qty - itemized_cnt
    return inv, itemized_cnt, bulk_pool

def preview_bulk_out(product: Product, warehouse: Warehouse, qty: int):
    """
    Dùng cho màn 'Preview': trả về (bulk_pool, itemized_cnt, lack, will_consume_itemized)
    """
    inv = Inventory.objects.filter(product=product, warehouse=warehouse).first()
    total = inv.qty if inv else 0
    itemized_cnt = get_itemized_count(product, warehouse)
    bulk_pool = max(0, total - itemized_cnt)
    lack = max(0, qty - bulk_pool)
    return {
        "total": total,
        "itemized_cnt": itemized_cnt,
        "bulk_pool": bulk_pool,
        "lack": lack,                      # thiếu so với bulk
        "will_consume_itemized": lack > 0, # nếu cho phép “bốc item”
    }

def allocate_bulk_out(product: Product, from_wh: Warehouse, qty: int, allow_consume_itemized=False):
    """
    Finalize: quyết định trừ từ bulk bao nhiêu và cần 'bốc' bao nhiêu Item.
    Trả về (bulk_used, picked_items:list[Item]).
    """
    with transaction.atomic():
        inv, itemized_cnt, bulk_pool = get_pools_locked(product, from_wh)
        if qty <= bulk_pool:
            return qty, []

        if not allow_consume_itemized:
            raise ValidationError(
                f"Không đủ hàng bulk để OUT {qty}. Còn bulk={bulk_pool}, itemized={itemized_cnt}."
            )

        need_items = qty - bulk_pool
        qs = (Item.objects
              .select_for_update()
              .filter(product=product, warehouse=from_wh, status="in_stock")
              .order_by("created_at", "id"))  # FIFO
        picked = list(qs[:need_items])
        if len(picked) < need_items:
            raise ValidationError(
                f"Không đủ hàng (kể cả item) để OUT {qty}. bulk={bulk_pool}, itemized={itemized_cnt}."
            )
        return bulk_pool, picked

# ==== Views cho Manual IN/OUT ====

def manual_start(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "OUT").upper()
        wh = Warehouse.objects.filter(id=request.POST.get("wh")).first()
        if action not in ("IN","OUT") or not wh:
            messages.error(request, "Chọn action (IN/OUT) và kho hợp lệ.")
            return redirect("manual_start")

        allow = bool(request.POST.get("allow_consume_itemized"))
        st = {
            "active": True,
            "action": action,
            "wh_id": wh.id,
            "allow_consume_itemized": allow,
            "lines": [],
            "batch_code": timezone.localtime().strftime("%Y%m%d-%H%M%S"),
        }
        _save_manual_batch(request, st)
        return redirect("manual_preview")

    # GET: render form start
    return render(request, "inventory/manual_start.html", {
        "warehouses": Warehouse.objects.all().order_by("code"),
        "subtab":"manual_start",
    })



@require_POST
def manual_add_line(request):
    st = _manual_batch(request)
    if not st.get("active"):
        messages.warning(request, "Chưa bắt đầu đơn thủ công.")
        return redirect("manual_start")

    sku = (request.POST.get("sku") or "").strip()
    qty = int(request.POST.get("qty") or 0)
    if not sku or qty <= 0:
        messages.error(request, "SKU/Qty không hợp lệ.")
        return redirect("manual_preview")

    product = Product.objects.filter(sku=sku).first()
    if not product:
        messages.error(request, f"Không tìm thấy SKU {sku}.")
        return redirect("manual_preview")

    st["lines"].append({"sku": sku, "qty": qty})
    _save_manual_batch(request, st)
    messages.success(request, f"Đã thêm {qty} x {sku}.")
    return redirect("manual_preview")

def manual_remove_line(request, idx: int):
    st = _manual_batch(request)
    if 0 <= idx < len(st.get("lines", [])):
        st["lines"].pop(idx)
        _save_manual_batch(request, st)
    return redirect("manual_preview")

def manual_clear(request):
    st = _manual_batch(request)
    st["lines"] = []
    _save_manual_batch(request, st)
    messages.info(request, "Đã xoá toàn bộ dòng trong batch.")
    return redirect("manual_preview")

def manual_preview(request):
    st = _manual_batch(request)
    if not st.get("active"):
        return redirect("manual_start")

    wh = Warehouse.objects.filter(id=st["wh_id"]).first()
    action = st["action"]
    allow = st.get("allow_consume_itemized", False)

    # ▼ lấy list product cho dropdown
    products = Product.objects.only("sku", "name").order_by("sku")

    # Tính preview & cảnh báo
    preview_rows = []
    total_warn = 0
    for i, ln in enumerate(st.get("lines", [])):
        product = Product.objects.filter(sku=ln["sku"]).first()
        qty = int(ln["qty"])
        row = {"idx": i, "sku": ln["sku"], "qty": qty, "valid": bool(product)}
        if product and action == "OUT":
            pv = preview_bulk_out(product, wh, qty)
            row.update(pv)
            row["status"] = "OK" if pv["lack"] == 0 else ("THIẾU (sẽ bốc item)" if allow else "THIẾU (sẽ bị chặn)")
            if pv["lack"] > 0 and not allow:
                total_warn += 1
        preview_rows.append(row)

    return render(request, "inventory/manual_preview.html", {
        "batch": st,
        "warehouse": wh,
        "preview_rows": preview_rows,
        "action": action,
        "allow_consume_itemized": allow,
        "has_blocking": (total_warn > 0) if action == "OUT" else False,
        "subtab": "manual_preview",
        "products": products,             # ◀️ thêm vào context
    })

@require_POST
@transaction.atomic
def manual_finalize(request):
    st = _manual_batch(request)
    if not st.get("active"):
        messages.warning(request, "Chưa bắt đầu đơn thủ công.")
        return redirect("manual_start")

    wh = Warehouse.objects.select_for_update().filter(id=st["wh_id"]).first()
    action = st["action"]
    allow = st.get("allow_consume_itemized", False)
    batch_id = st.get("batch_code") or timezone.localtime().strftime("%Y%m%d-%H%M%S")

    created_moves = 0
    # Duyệt từng dòng
    for ln in st.get("lines", []):
        product = Product.objects.filter(sku=ln["sku"]).first()
        if not product:
            continue
        qty = int(ln["qty"])

        if action == "IN":
            # IN bulk: tăng tồn kho, log Move bulk
            mv = Move.objects.create(
                product=product, quantity=qty, action="IN", to_wh=wh,
                type_action="MANUAL", note="IN (manual bulk)", batch_id=batch_id
            )
            # cập nhật tồn (dùng helper có sẵn của bạn)
            adjust_inventory(product, wh, +qty)
            created_moves += 1

        else:  # OUT
            # Quyết định dùng bulk &/hoặc bốc item
            bulk_used, picked_items = allocate_bulk_out(product, wh, qty, allow_consume_itemized=allow)

            if bulk_used > 0:
                mvb = Move.objects.create(
                    product=product, quantity=bulk_used, action="OUT", from_wh=wh,
                    type_action="MANUAL", note="OUT (manual bulk)", batch_id=batch_id
                )
                adjust_inventory(product, wh, -bulk_used)
                created_moves += 1

            for it in picked_items:
                mvi = Move.objects.create(
                    item=it, action="OUT", from_wh=wh,
                    type_action="MANUAL", note="OUT (manual picked)", batch_id=batch_id
                )
                # cập nhật tồn + trạng thái item (theo scan_move bạn đang làm)
                adjust_inventory(it.product, wh, -1)
                it.warehouse = None
                it.status = "shipped"
                it.save(update_fields=["warehouse","status"])
                created_moves += 1

    # Reset batch + hiển thị link truy xuất
    request.session["manual_batch"] = {"active": False, "lines": []}
    request.session.modified = True
    messages.success(request, f"Đã ghi sổ batch {batch_id} với {created_moves} giao dịch.")
    return redirect(f"{reverse('manual_batch_detail')}?batch={batch_id}")

def manual_batch_detail(request):
    batch_id = (request.GET.get("batch") or "").strip()
    if not batch_id:
        return render(request, "inventory/manual_batch_detail.html", {"batch_id": "", "moves": []})

    moves = (Move.objects
             .select_related("item__product","from_wh","to_wh","product")
             .filter(batch_id=batch_id)
             .order_by("created_at","id"))

    return render(request, "inventory/manual_batch_detail.html", {
        "batch_id": batch_id,
        "moves": moves,
        "total": moves.count(),
        "subtab": "manual_batch",  
    })
# ---------- Generate labels ----------

@transaction.atomic
def generate_labels(request):
    if request.method == "POST":
        form = GenerateForm(request.POST)
        if form.is_valid():
            sku = form.cleaned_data["sku"].strip()
            name = form.cleaned_data["name"].strip()
            qty = int(form.cleaned_data["qty"])
            import_date = form.cleaned_data["import_date"]  # dd/mm/yyyy -> Date

            # sync tên SP nếu đã có
            product, created = Product.objects.get_or_create(sku=sku, defaults={"name": name})
            if not created and name and product.name != name:
                product.name = name
                product.save(update_fields=["name"])

            # Đưa vào giỏ (chưa tạo Item)
            queue = _get_queue(request)
            queue.append({
                "sku": sku,
                "name": name,
                "qty": qty,
                "import_date": import_date.strftime("%d/%m/%Y"),
            })
            _save_queue(request, queue)

            messages.success(request, f"Đã thêm {qty} tem cho SKU {sku} vào giỏ in.")
            return redirect("generate_labels")
        else:
            messages.error(request, "Form không hợp lệ. Kiểm tra lại dữ liệu.")
    else:
        form = GenerateForm()

    products = list(Product.objects.values("sku", "name").order_by("sku"))

    # Panel “đã tạo batch”
    last_batch = request.GET.get("batch")
    if last_batch:
        # batch mới: YYYYMMDD-HHMMSS (không còn -SKU)
        if not re.match(r"^\d{8}-\d{6}$", last_batch):
            last_batch = None
        else:
            d = Path(settings.MEDIA_ROOT) / "labels" / last_batch
            if not d.is_dir():
                last_batch = None

    queue = _get_queue(request)
    total_qty = sum(int(r["qty"]) for r in queue) if queue else 0

    return render(
        request,
        "inventory/generate.html",
        {
            "form": form,
            "products": products,
            "last_batch": last_batch,
            "media_url": settings.MEDIA_URL,
            "queue": queue,
            "total_qty": total_qty,
        },
    )

def remove_queue_line(request, idx: int):
    queue = _get_queue(request)
    if 0 <= idx < len(queue):
        removed = queue.pop(idx)
        _save_queue(request, queue)
        messages.info(request, f"Đã xóa SKU {removed['sku']} khỏi giỏ in.")
    return redirect("generate_labels")


def clear_queue(request):
    _save_queue(request, [])
    messages.info(request, "Đã xóa toàn bộ giỏ in.")
    return redirect("generate_labels")

@transaction.atomic
def finalize_queue(request):
    queue = _get_queue(request)
    if not queue:
        messages.warning(request, "Giỏ in đang trống.")
        return redirect("generate_labels")

    # Tạo batch: YYYYMMDD-HHMMSS
    batch_code = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    batch_dir = MEDIA_ROOT / "labels" / batch_code
    batch_dir.mkdir(parents=True, exist_ok=True)

    total_created = 0
    for row in queue:
        sku = row["sku"]
        name = row["name"]
        qty = int(row["qty"])
        import_dt = datetime.strptime(row["import_date"], "%d/%m/%Y").date()

        product, _ = Product.objects.get_or_create(sku=sku, defaults={"name": name})

        sku_dir = batch_dir / sku
        sku_dir.mkdir(exist_ok=True)

        for _ in range(qty):
            item = Item.objects.create(product=product, import_date=import_dt)
            save_code128_png(item.barcode_text, product.name, out_dir=str(sku_dir))
            total_created += 1

    # Gói ZIP ra đĩa
    zip_file = batch_dir / f"{batch_code}.zip"
    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in batch_dir.rglob("*.png"):
            zf.write(p, arcname=str(p.relative_to(batch_dir)))
        zf.writestr(
            "MANIFEST.txt",
            f"Batch: {batch_code}\nGenerated at: {timezone.localtime():%Y-%m-%d %H:%M:%S}\nFiles: {total_created}\n"
        )

    # Xoá giỏ sau khi build ZIP
    _save_queue(request, [])

    # ▶️ Trả file luôn (download ngay), không redirect về /generate/
    return FileResponse(open(zip_file, "rb"), as_attachment=True, filename=f"{batch_code}.zip")

def download_batch(request, batch: str):
    """
    Tải ZIP: MEDIA_ROOT/labels/<batch>/<batch>.zip
    batch: YYYYMMDD-HHMMSS
    """
    if not re.match(r"^\d{8}-\d{6}$", batch or ""):
        return HttpResponseBadRequest("Bad batch name.")

    zip_path = MEDIA_ROOT / "labels" / batch / f"{batch}.zip"
    if not zip_path.exists():
        raise Http404("Batch not found.")

    data = zip_path.read_bytes()
    resp = HttpResponse(data, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{batch}.zip"'
    return resp

# ---------- Scan & Move ----------
# @transaction.atomic

# ---------- Tiện ích phiên quét ----------


def _scan_state(request):
    """Trạng thái phiên quét lưu trong session."""
    return request.session.setdefault("scan_session", {"active": False, "scanned": []})

def _save_scan_state(request, st):
    request.session["scan_session"] = st
    request.session.modified = True

def _tag_max_today(action: str, wh) -> int:
    today = timezone.localdate()
    qs = Move.objects.filter(action=action, created_at__date=today)
    qs = qs.filter(to_wh=wh) if action == "IN" else qs.filter(from_wh=wh)
    return qs.aggregate(m=Max("tag"))["m"] or 0   # dùng alias 'm'
    # (hoặc: return qs.aggregate(Max("tag"))["tag__max"] or 0)



# ---------- Bắt đầu / kết thúc phiên ----------

@transaction.atomic
def scan_start(request):
    if request.method != "POST":
        return redirect("scan_scan")

    from .forms import ScanStartForm
    # bước 1: đọc sơ bộ action + kho để biết tag_max
    act = (request.POST.get("action") or "IN").upper()
    wh_id = request.POST.get("wh")
    wh = Warehouse.objects.filter(id=wh_id).first()
    tag_max = _tag_max_today(act, wh) + 1 if wh else 1

    form = ScanStartForm(request.POST, tag_max=tag_max)
    if not form.is_valid():
        for e in form.errors.values(): messages.error(request, e)
        return redirect("scan_scan")

    action = form.cleaned_data["action"]
    type_action = form.cleaned_data["action_type"]
    wh = form.cleaned_data["wh"]

    # ràng buộc tag: 1..(max+1)
    max_allowed = _tag_max_today(action, wh) + 1
    try_tag = int(request.POST.get("tag") or max_allowed)
    tag = try_tag if 1 <= try_tag <= max_allowed else max_allowed

    st = {
        "active": True,
        "action": action,
        "type_action": type_action,
        "wh_id": wh.id,
        "tag": tag,
        "started_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scanned": [],
    }
    _save_scan_state(request, st)
    messages.success(request, f"Bắt đầu ghi — {action} / Kho {wh.code} / Đợt #{tag}.")
    return redirect("scan_scan")

def scan_stop(request):
    if request.method != "POST":
        return redirect("scan_scan")
    st = _scan_state(request)
    st["active"] = False
    _save_scan_state(request, st)
    messages.info(request, "Đã kết thúc ghi.")
    return redirect("scan_scan")
# ---------- Trang Scan & Check ----------
@transaction.atomic
def scan_move(request):
    st = _scan_state(request)

    # POST barcode trong phiên
    if request.method == "POST" and "barcode" in request.POST:
        if not st.get("active"):
            messages.warning(request, "Chưa bắt đầu phiên quét.")
            return redirect("scan_scan")

        code = request.POST.get("barcode", "").strip()
        if not code: return redirect("scan_scan")

        action = st["action"]
        type_action = st.get("type_action") or ""
        tag = int(st.get("tag") or 1)
        wh = Warehouse.objects.filter(id=st.get("wh_id")).first()

        try:
            item = (Item.objects.select_for_update()
                    .select_related("product","warehouse")
                    .get(barcode_text=code))
        except Item.DoesNotExist:
            messages.error(request, f"Không tìm thấy barcode: {code}")
            return redirect("scan_scan")

        if action == "IN":
            # if not wh:
            #     messages.error(request, "IN cần chọn kho.")
            #     return redirect("scan_scan")
            if item.warehouse:
                messages.warning(request, f"{code} đang ở {item.warehouse.code}.")
                return redirect("scan_scan")
            Move.objects.create(item=item, action="IN", to_wh=wh,
                                type_action=type_action, tag=tag, note="IN (scan)")
            item.warehouse = wh; item.status = "in_stock"
            item.save(update_fields=["warehouse","status"])
            adjust_inventory(item.product, wh, +1)
            messages.success(request, f"IN {code} → {wh.code}")

        else:  # OUT
            if not item.warehouse:
                messages.warning(request, f"{code} đã OUT trước đó.")
                return redirect("scan_scan")
            if wh and item.warehouse != wh:
                messages.warning(request, f"{code} đang ở {item.warehouse.code}, khác kho phiên ({wh.code}).")
                return redirect("scan_scan")
            base_wh = wh or item.warehouse
            Move.objects.create(item=item, action="OUT", from_wh=base_wh,
                                type_action=type_action, tag=tag, note="OUT (scan)")
            adjust_inventory(item.product, base_wh, -1)
            item.warehouse = None; item.status = "shipped"
            item.save(update_fields=["warehouse","status"])
            messages.success(request, f"OUT {code}")

        st["scanned"] = [code] + st.get("scanned", [])[:19]
        _save_scan_state(request, st)
        return redirect("scan_scan")

    # GET: render + cung cấp TAG_MAP để JS tự nhảy số theo kho/action
    from .forms import ScanStartForm, ScanCodeForm
    # build tag_map: {"IN-<wh_id>": max, "OUT-<wh_id>": max}
    tag_map = {}
    today = timezone.localdate()
    for wh in Warehouse.objects.all():
        in_max = (Move.objects
                .filter(action="IN", to_wh=wh, created_at__date=today)
                .aggregate(m=Max("tag"))["m"] or 0)
        out_max = (Move.objects
               .filter(action="OUT", from_wh=wh, created_at__date=today)
               .aggregate(m=Max("tag"))["m"] or 0)
        tag_map[f"IN-{wh.id}"]  = in_max
        tag_map[f"OUT-{wh.id}"] = out_max

    start_form = ScanStartForm(initial={
        "action": st.get("action") or "IN",
        "action_type": st.get("type_action") or "",
        "wh": Warehouse.objects.filter(id=st.get("wh_id")).first() if st.get("wh_id") else None,
        "tag": st.get("tag") or 1,
    }, tag_max=(st.get("tag") or 1))

    code_form = ScanCodeForm()
    return render(request, "inventory/scan_move.html", {
        "start_form": start_form,
        "code_form": code_form,
        "scan_session": st,
        "tag_map": tag_map,   # ✨ gửi cho template
        "subtab": "scan", 
    })
# ---------- Phân tích ----------
def inventory_view(request):
    data = (
        Inventory.objects.select_related("product", "warehouse")
        .values("warehouse__code", "product__sku", "product__name", "qty")
        .order_by("warehouse__code", "product__sku")
    )
    return render(request, "inventory/inventory.html", {"inv": data})


def transactions(request):
    logs = Move.objects.select_related(
        "item", "item__product", "from_wh", "to_wh"
    ).all()[:500]
    return render(request, "inventory/transactions.html", {"logs": logs})


def barcode_lookup(request):
    item = None
    moves = []
    if request.method == "POST":
        code = request.POST.get("barcode", "").strip()
        try:
            item = Item.objects.select_related("product", "warehouse").get(
                barcode_text=code
            )
            moves = item.moves.select_related("from_wh", "to_wh").all()
        except Item.DoesNotExist:
            messages.error(request, "Không tìm thấy barcode.")
    return render(request, "inventory/scan_check.html", {
        "item": item,
        "moves": moves,
        "subtab": "check",  # ✨ để tab Check sáng
    })



# ---------- CRUD Product ----------
def product_list(request):
    q = request.GET.get("q", "").strip()
    qs = Product.objects.all()
    if q:
        qs = qs.filter(
            Q(sku__icontains=q) |
            Q(name__icontains=q) |
            Q(code4__icontains=q)
        )
    return render(request, "inventory/product_list.html", {"products": qs, "q": q})


def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            try:
                form.save()  # tự sinh code4 trong model.save()
                messages.success(request, "Tạo sản phẩm thành công.")
                return redirect(reverse("product_list"))
            except Exception as e:
                messages.error(request, f"Lỗi: {e}")
    else:
        form = ProductForm()
    return render(request, "inventory/product_form.html", {"form": form, "title": "Tạo sản phẩm"})

def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            try:
                form.save()  # code4 giữ nguyên
                messages.success(request, "Cập nhật sản phẩm thành công.")
                return redirect(reverse("product_list"))
            except Exception as e:
                messages.error(request, f"Lỗi: {e}")
    else:
        form = ProductForm(instance=product)
    return render(request, "inventory/product_form.html", {"form": form, "title": f"Sửa: {product.sku}", "product": product})

def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Đã xoá sản phẩm.")
        return redirect(reverse("product_list"))
    return render(request, "inventory/product_confirm_delete.html", {"product": product})

# ---------- Query Panel ----------
# def _execute_sql(sql: str):
#     """
#     Cho phép chạy SELECT/INSERT/UPDATE/DELETE/PRAGMA... có kiểm soát:
#     chỉ chấp nhận khi từ đầu tiên thuộc whitelist.
#     """
#     allowed = (
#         "select",
#         "with",
#         "insert",
#         "update",
#         "delete",
#         "replace",
#         "pragma",
#         "begin",
#         "commit",
#         "rollback",
#     )
#     if not re.match(r"^\s*(" + "|".join(allowed) + r")\b", sql, flags=re.IGNORECASE | re.DOTALL):
#         raise ValueError("Chỉ cho phép: " + ", ".join(allowed))

#     with connection.cursor() as cur:
#         cur.execute(sql)
#         cols = [c[0] for c in cur.description] if cur.description else []
#         rows = cur.fetchall() if cur.description else []
#     return cols, rows

def _execute_sql(sql: str):
    """
    Cho phép chạy SELECT/WITH/INSERT/UPDATE/DELETE/REPLACE/PRAGMA/BEGIN/COMMIT/ROLLBACK.
    Trả về (cols, rows, affected):
      - Nếu là SELECT/WITH: trả cols + rows, affected = len(rows)
      - Nếu là lệnh ghi:   cols=[], rows=[], affected = rowcount (nếu có)
    """
    allowed = (
        "select", "with", "insert", "update", "delete",
        "replace", "pragma", "begin", "commit", "rollback",
    )
    if not re.match(r"^\s*(" + "|".join(allowed) + r")\b",
                    sql, flags=re.IGNORECASE | re.DOTALL):
        raise ValueError("Chỉ cho phép: " + ", ".join(allowed))

    # (tuỳ chọn) Chặn multi-statements để an toàn hơn
    # if ";" in sql.strip().rstrip(";"):
    #     raise ValueError("Chỉ chạy 1 câu lệnh mỗi lần.")

    with connection.cursor() as cur:
        cur.execute(sql)
        if cur.description:  # SELECT/WITH trả về dữ liệu
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
            affected = len(rows)
        else:                # INSERT/UPDATE/DELETE...
            cols, rows = [], []
            affected = cur.rowcount if getattr(cur, "rowcount", -1) != -1 else None
    return cols, rows, affected


def _list_db_tables_with_type():
    """
    Lấy danh sách bảng + loại (table/view). Ưu tiên SQLite sqlite_master
    để có cả VIEW; fallback introspection cho DB khác.
    Trả về: [{"name": "...", "type": "BASE TABLE" | "VIEW"}, ...]
    """
    items = []
    try:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT name, type
                FROM sqlite_master
                WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            rows = cur.fetchall()
            for name, tp in rows:
                items.append({
                    "name": name,
                    "type": "BASE TABLE" if tp == "table" else "VIEW"
                })
    except Exception:
        # DB khác SQLite
        for name in sorted(connection.introspection.table_names()):
            items.append({"name": name, "type": "BASE TABLE"})
    return items

# views.py
def _execute_sql(sql: str):
    """
    Cho phép chạy SELECT/INSERT/UPDATE/DELETE/PRAGMA... có kiểm soát:
    chỉ chấp nhận khi từ đầu tiên thuộc whitelist.
    """
    allowed = (
        "select", "with", "insert", "update", "delete",
        "replace", "pragma", "begin", "commit", "rollback",
    )
    if not re.match(r"^\s*(" + "|".join(allowed) + r")\b", sql,
                    flags=re.IGNORECASE | re.DOTALL):
        raise ValueError("Chỉ cho phép: " + ", ".join(allowed))

    with connection.cursor() as cur:
        cur.execute(sql)
        if cur.description:          # SELECT … => có kết quả
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
            rowcount = len(rows)
        else:                         # INSERT/UPDATE/DELETE … => không có result set
            cols, rows = [], []
            rowcount = cur.rowcount   # số dòng bị ảnh hưởng
    return cols, rows, rowcount



# views.py
def query_panel(request):
    tables = _list_db_tables_with_type()
    table_names = [t["name"] for t in tables]
    selected = request.GET.get("table")
    if selected not in table_names:
        selected = table_names[0] if table_names else None

    # Clear -> về mặc định
    if request.GET.get("clear") == "1":
        return redirect(f"{request.path}?table={selected}" if selected else request.path)

    # SQL mặc định (preview bảng)
    if request.method == "POST":
        sql_text = (request.POST.get("sql") or "").strip()
    else:
        sql_text = f"SELECT * FROM {selected} LIMIT 100" if selected else ""

    # Lấy danh sách cột của bảng đang xem
    columns = None
    if selected:
        try:
            with connection.cursor() as cur:
                desc = connection.introspection.get_table_description(cur, selected)
                columns = [d.name for d in desc]
        except Exception:
            columns = None

    # Run query
    result = None
    error = None
    rows_count = None
    affected_count = None   # ✨ thêm biến này
    status_text = None

    if request.method == "POST":
        try:
            cols, rows, rc = _execute_sql(sql_text)
            if cols:  # có result set -> SELECT/WITH
                result = {"cols": cols, "rows": rows}
                rows_count = len(rows)
                status_text = f"Query executed successfully. {rows_count} rows returned."
            else:     # không có result set -> INSERT/UPDATE/DELETE...
                affected_count = rc
                rows_count = 0
                status_text = f"Query executed successfully. {rc} rows affected."
            messages.success(request, status_text)
        except Exception as e:
            error = str(e)
    else:
        # GET: preview bảng đang chọn
        if selected:
            try:
                cols, rows = _execute_select_sql(f"SELECT * FROM {selected} LIMIT 100")
                result = {"cols": cols, "rows": rows}
                rows_count = len(rows)
                status_text = f"Query executed successfully. {rows_count} rows returned."
            except Exception as e:
                error = str(e)

    # Lấy type của bảng đang chọn
    selected_type = None
    for t in tables:
        if t["name"] == selected:
            selected_type = t["type"]
            break

    ctx = {
        "tables": tables,
        "selected": selected,
        "selected_type": selected_type,
        "columns": columns,
        "sql": sql_text,
        "result": result,
        "error": error,
        "rows_count": rows_count,
        "affected_count": affected_count,  # ✨ đẩy ra template
        "status_text": status_text,
    }
    return render(request, "inventory/query_panel.html", ctx)

