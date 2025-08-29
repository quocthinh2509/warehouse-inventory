"""
API versions of all views from views.py - returns JSON responses
"""
from pathlib import Path
import re, io, zipfile
import csv, unicodedata
import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db import transaction, connection
from django.db.models import Q, Max, Count, Sum, F, Avg, Case, When, Value, IntegerField, CharField
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from urllib.parse import quote
from django.db.models.functions import Extract, TruncHour
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from datetime import datetime, date, timedelta
from shutil import make_archive
from .models import Product, Warehouse, Item, Inventory, Move, SavedQuery
from .forms import GenerateForm, ScanMoveForm, ProductForm, SQLQueryForm
from .utils import make_payload, save_code128_png
from io import StringIO

MEDIA_ROOT = Path(settings.MEDIA_ROOT)

try:
    from openpyxl import load_workbook   # pip install openpyxl
except Exception:
    load_workbook = None

# ---------- API versions of main views ----------

@require_GET
def api_index(request):
    """API version of index"""
    return JsonResponse({
        'status': 'success',
        'message': 'Warehouse Inventory API',
        'redirect': 'generate_labels'
    })

@require_GET
def api_config_index(request):
    """API version of config_index"""
    return JsonResponse({
        'status': 'success',
        'message': 'Config hub with 3 modules',
        'modules': ['Query Panel', 'Products', 'Admin']
    })

@require_GET
def api_dashboard_redirect(request):
    """API version of dashboard_redirect"""
    return JsonResponse({
        'status': 'success',
        'redirect': 'dashboard_warehouse'
    })

# -------- API version of dashboard warehouse ---------

@require_GET
def api_dashboard_warehouse(request):
    """API version of dashboard_warehouse"""
    wh_id = request.GET.get("wh") or ""
    q = (request.GET.get("q") or "").strip()
    per = int(request.GET.get("per") or 50)
    page_num = int(request.GET.get("page") or 1)

    warehouses = list(Warehouse.objects.all().order_by("code").values('id', 'code', 'name'))

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
    page = pager.get_page(page_num)

    # Statistics for today
    today = timezone.now().date()
    move_today_qs = Move.objects.filter(created_at__date=today)
    
    if wh_id:
        move_today_qs = move_today_qs.filter(
            Q(from_wh_id=wh_id) | Q(to_wh_id=wh_id)
        )
    
    today_in = move_today_qs.filter(action='IN').count()
    today_out = move_today_qs.filter(action='OUT').count()

    return JsonResponse({
        'status': 'success',
        'data': {
            'active_tab': 'warehouse',
            'warehouses': warehouses,
            'wh_id': str(wh_id),
            'q': q,
            'per': per,
            'per_options': [25, 50, 100, 200],
            'inventory_items': list(page.object_list),
            'pagination': {
                'current_page': page.number,
                'total_pages': page.paginator.num_pages,
                'total_items': page.paginator.count,
                'has_previous': page.has_previous(),
                'has_next': page.has_next(),
            },
            'statistics': {
                'total_skus': len(set(r["product__sku"] for r in rows)),
                'total_qty': sum(r["qty"] or 0 for r in rows),
                'today_in': today_in,
                'today_out': today_out,
            }
        }
    })

# ---- API version of Barcodes Dashboard

@require_GET
def api_dashboard_barcodes(request):
    """API version of dashboard_barcodes"""
    q = (request.GET.get('q') or '').strip()
    wh = request.GET.get('wh') or ''
    status = request.GET.get('status') or ''
    date_from = request.GET.get('date_from') or ''
    date_to = request.GET.get('date_to') or ''
    per = int(request.GET.get('per') or 50)
    page_num = int(request.GET.get('page') or 1)

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
    page = paginator.get_page(page_num)

    # Warehouses for dropdown
    warehouses = list(Warehouse.objects.all().order_by('code').values('id', 'code', 'name'))

    # Convert items to dict
    items_data = []
    for item in page.object_list:
        items_data.append({
            'id': item.id,
            'barcode_text': item.barcode_text,
            'product_sku': item.product.sku if item.product else '',
            'product_name': item.product.name if item.product else '',
            'warehouse_code': item.warehouse.code if item.warehouse else '',
            'status': item.status,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'import_date': item.import_date.isoformat() if item.import_date else None,
        })

    return JsonResponse({
        'status': 'success',
        'data': {
            'active_tab': 'barcodes',
            'items': items_data,
            'warehouses': warehouses,
            'filters': {
                'q': q,
                'wh': wh,
                'status': status,
                'date_from': date_from,
                'date_to': date_to,
                'per': per,
                'per_options': [25, 50, 100, 200, 500]
            },
            'pagination': {
                'current_page': page.number,
                'total_pages': page.paginator.num_pages,
                'total_items': page.paginator.count,
                'has_previous': page.has_previous(),
                'has_next': page.has_next(),
            },
            'statistics': {
                'total_items': total_items,
                'in_stock_count': in_stock_count,
                'shipped_count': shipped_count,
                'today_created': today_created,
                'unique_products': unique_products,
                'active_warehouses': active_warehouses,
            }
        }
    })

# ---- API version of History Dashboard

@require_GET
def api_dashboard_history(request):
    """API version of dashboard_history"""
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

    # Base queryset
    qs = (
        Move.objects.select_related("item__product", "product", "from_wh", "to_wh")
        .prefetch_related("item__product")
    )

    # Apply filters
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
            Q(product__sku__icontains=q) |
            Q(product__name__icontains=q) |
            Q(batch_id__icontains=q) |
            Q(note__icontains=q) |
            Q(type_action__icontains=q)
        )

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
            When(product__isnull=False, then=F("quantity")),
            default=Value(1),
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

    # Convert to JSON serializable format
    logs_data = []
    for log in logs:
        logs_data.append({
            'id': log.id,
            'created_at': log.created_at.isoformat(),
            'kind': log.u_kind,
            'barcode': log.u_barcode,
            'sku': log.u_sku,
            'name': log.u_name,
            'qty': log.u_qty,
            'action': log.action,
            'from_wh': log.from_wh.code if log.from_wh else None,
            'to_wh': log.to_wh.code if log.to_wh else None,
            'type_action': log.type_action,
            'note': log.note,
            'tag': log.tag,
            'batch_id': log.batch_id,
        })

    # Analytics calculation (simplified)
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

    warehouses = list(Warehouse.objects.all().order_by("code").values('id', 'code', 'name'))

    return JsonResponse({
        'status': 'success',
        'data': {
            'active_tab': 'history',
            'logs': logs_data,
            'total_rows': total_rows,
            'statistics': {
                'total_in_qty': total_in_qty,
                'total_out_qty': total_out_qty,
            },
            'filters': {
                'q': q,
                'action': action,
                'wh_id': str(wh_id),
                'start': start_s,
                'end': end_s,
                'sort': sort,
                'dir': dir_,
                'per': per,
            },
            'warehouses': warehouses,
            'per_options': [100, 200, 500, 1000, 2000],
            'quick_dates': {
                'today': today.strftime("%Y-%m-%d"),
                'yesterday': yesterday.strftime("%Y-%m-%d"),
                'week_start': week_start.strftime("%Y-%m-%d"),
                'month_start': month_start.strftime("%Y-%m-%d"),
            }
        }
    })

# -------- API versions of Manual Process Views --------

@csrf_exempt
@require_POST
def api_manual_start(request):
    """API version of manual_start"""
    try:
        # Clear any existing queue
        request.session["manual_queue"] = []
        return JsonResponse({
            'status': 'success',
            'message': 'Manual process started',
            'queue_size': 0
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@csrf_exempt
@require_POST
def api_manual_add_line(request):
    """API version of manual_add_line"""
    try:
        data = json.loads(request.body)
        sku = data.get('sku', '').strip()
        qty = int(data.get('qty', 1))
        wh_code = data.get('warehouse', '').strip()
        
        if not sku or not wh_code:
            return JsonResponse({
                'status': 'error',
                'message': 'SKU and warehouse are required'
            }, status=400)
        
        # Get or create product
        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Product with SKU {sku} not found'
            }, status=404)
        
        # Get warehouse
        try:
            warehouse = Warehouse.objects.get(code=wh_code)
        except Warehouse.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Warehouse {wh_code} not found'
            }, status=404)
        
        # Get current queue
        queue = request.session.get("manual_queue", [])
        
        # Add to queue
        queue.append({
            'sku': sku,
            'name': product.name,
            'qty': qty,
            'warehouse': wh_code,
        })
        
        request.session["manual_queue"] = queue
        request.session.modified = True
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item added to queue',
            'queue_size': len(queue),
            'item': {
                'sku': sku,
                'name': product.name,
                'qty': qty,
                'warehouse': wh_code,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@csrf_exempt 
@require_POST
def api_manual_remove_line(request, idx):
    """API version of manual_remove_line"""
    try:
        queue = request.session.get("manual_queue", [])
        
        if 0 <= idx < len(queue):
            removed_item = queue.pop(idx)
            request.session["manual_queue"] = queue
            request.session.modified = True
            
            return JsonResponse({
                'status': 'success',
                'message': 'Item removed from queue',
                'queue_size': len(queue),
                'removed_item': removed_item
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid index'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@csrf_exempt
@require_POST  
def api_manual_clear(request):
    """API version of manual_clear"""
    try:
        request.session["manual_queue"] = []
        request.session.modified = True
        
        return JsonResponse({
            'status': 'success',
            'message': 'Queue cleared',
            'queue_size': 0
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@require_GET
def api_manual_preview(request):
    """API version of manual_preview"""
    try:
        queue = request.session.get("manual_queue", [])
        
        # Calculate totals
        total_items = len(queue)
        total_qty = sum(item['qty'] for item in queue)
        
        # Group by warehouse
        by_warehouse = {}
        for item in queue:
            wh = item['warehouse']
            if wh not in by_warehouse:
                by_warehouse[wh] = []
            by_warehouse[wh].append(item)
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'queue': queue,
                'statistics': {
                    'total_items': total_items,
                    'total_qty': total_qty,
                },
                'by_warehouse': by_warehouse,
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

# -------- Placeholder API functions for remaining views --------

@require_GET
def api_manual_finalize(request):
    """API version of manual_finalize - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for manual_finalize - implementation needed'
    })

@require_GET
def api_manual_batch_detail(request):
    """API version of manual_batch_detail - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for manual_batch_detail - implementation needed'
    })

@require_GET
def api_generate_labels(request):
    """API version of generate_labels - placeholder"""
    return JsonResponse({
        'status': 'info', 
        'message': 'API endpoint for generate_labels - implementation needed'
    })

@require_POST
def api_remove_queue_line(request, idx):
    """API version of remove_queue_line - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': f'API endpoint for remove_queue_line idx={idx} - implementation needed'
    })

@require_POST
def api_clear_queue(request):
    """API version of clear_queue - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for clear_queue - implementation needed'
    })

@require_POST
def api_finalize_queue(request):
    """API version of finalize_queue - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for finalize_queue - implementation needed'
    })

@require_GET
def api_download_batch(request, batch):
    """API version of download_batch - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': f'API endpoint for download_batch batch={batch} - implementation needed'
    })

@require_POST
def api_scan_start(request):
    """API version of scan_start - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for scan_start - implementation needed'
    })

@require_POST
def api_scan_stop(request):
    """API version of scan_stop - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for scan_stop - implementation needed'
    })

@require_POST
def api_scan_move(request):
    """API version of scan_move - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for scan_move - implementation needed'
    })

@require_GET
def api_inventory_view(request):
    """API version of inventory_view - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for inventory_view - implementation needed'
    })

@require_GET 
def api_transactions(request):
    """API version of transactions - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for transactions - implementation needed'
    })

@require_GET
def api_barcode_lookup(request):
    """API version of barcode_lookup - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for barcode_lookup - implementation needed'
    })

# -------- API versions of Product CRUD --------

@require_GET
def api_product_list(request):
    """API version of product_list - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for product_list - implementation needed'
    })

@csrf_exempt
@require_POST
def api_product_create(request):
    """API version of product_create - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for product_create - implementation needed'
    })

@csrf_exempt
def api_product_update(request, pk):
    """API version of product_update - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': f'API endpoint for product_update pk={pk} - implementation needed'
    })

@csrf_exempt
@require_POST
def api_product_delete(request, pk):
    """API version of product_delete - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': f'API endpoint for product_delete pk={pk} - implementation needed'
    })

@csrf_exempt
def api_query_panel(request, pk=None):
    """API version of query_panel - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': f'API endpoint for query_panel pk={pk} - implementation needed'
    })

@csrf_exempt
def api_manual_upload(request):
    """API version of manual_upload - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for manual_upload - implementation needed'
    })

@require_GET
def api_manual_sample_csv(request):
    """API version of manual_sample_csv - placeholder"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for manual_sample_csv - implementation needed'
    })

# -------- Export functions --------

@require_GET
def api_export_barcodes_csv(request):
    """API version of export_barcodes_csv - returns JSON with download URL or data"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for export_barcodes_csv - implementation needed'
    })

@require_GET
def api_export_history_csv(request):
    """API version of export_history_csv - returns JSON with download URL or data"""
    return JsonResponse({
        'status': 'info',
        'message': 'API endpoint for export_history_csv - implementation needed'
    })