from pathlib import Path
import re, io, zipfile

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, connection
from django.db.models import Q, Max
from django.contrib import messages
from django.utils import timezone
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from urllib.parse import quote

from shutil import make_archive
from .models import Product, Warehouse, Item, Inventory, Move, SavedQuery
from .forms import GenerateForm, ScanMoveForm, ProductForm, SQLQueryForm
from .utils import make_payload, save_code128_png


# ---------- Trang chính & Dashboard ----------
def index(request):
    return render(request, "inventory/index.html")


def dashboard(request):
    total_in = Move.objects.filter(action="IN").count()
    total_out = Move.objects.filter(action="OUT").count()
    total_transfer = Move.objects.filter(action="TRANSFER").count()
    logs = (
        Move.objects.select_related("item", "item__product", "from_wh", "to_wh")
        .all()[:200]
    )
    return render(
        request,
        "inventory/dashboard.html",
        {
            "total_in": total_in,
            "total_out": total_out,
            "total_transfer": total_transfer,
            "logs": logs,
        },
    )


# ---------- Helper tồn kho ----------
def adjust_inventory(product: Product, warehouse: Warehouse, delta: int):
    """Điều chỉnh tồn kho, không cho âm."""
    inv, _ = Inventory.objects.get_or_create(
        product=product, warehouse=warehouse, defaults={"qty": 0}
    )
    inv.qty = max(0, inv.qty + delta)
    inv.save(update_fields=["qty"])


# ---------- Generate labels ----------

@transaction.atomic
def generate_labels(request):
    if request.method == "POST":
        form = GenerateForm(request.POST)
        if form.is_valid():
            sku = form.cleaned_data["sku"].strip()
            name = form.cleaned_data["name"].strip()
            qty = form.cleaned_data["qty"]
            mark_in = form.cleaned_data["mark_in"]
            wh = form.cleaned_data["warehouse"] if mark_in else None

            # Product
            product, created = Product.objects.get_or_create(sku=sku, defaults={"name": name})
            if not created and name and product.name != name:
                product.name = name
                product.save(update_fields=["name"])

            # seq bắt đầu
            max_seq = Item.objects.filter(product=product).aggregate(m=Max("seq"))["m"] or 0
            seq_start = max_seq + 1

            # Thư mục batch
            batch_dirname = f"{timezone.now():%Y%m%d-%H%M%S}-{sku}"
            out_dir = Path(settings.MEDIA_ROOT) / "labels" / batch_dirname
            out_dir.mkdir(parents=True, exist_ok=True)

            # Tạo tem + (tuỳ chọn) ghi IN
            for i in range(qty):
                seq = seq_start + i
                payload = make_payload(sku, seq)

                item = Item.objects.create(
                    product=product,
                    seq=seq,
                    barcode_text=payload,
                    warehouse=wh if mark_in else None,
                )

                if mark_in and wh:
                    Move.objects.create(
                        item=item, action="IN", to_wh=wh,
                        note=f"Nhập kho & in tem ({batch_dirname})"
                    )
                    adjust_inventory(product, wh, +1)

                save_code128_png(payload, product.name, out_dir=str(out_dir))

            messages.success(request, f"Đã tạo {qty} tem. Bạn có thể tải ZIP ở dưới.")
            # Redirect lại để hiện nút tải
            return redirect(f"{reverse('generate_labels')}?batch={batch_dirname}")
    else:
        form = GenerateForm()

    # Dữ liệu cho auto-fill SKU<->Tên
    products = list(Product.objects.values("sku", "name").order_by("sku"))

    # Nếu có ?batch=... -> hiển thị nút Download
    last_batch = request.GET.get("batch")
    if last_batch:
        # kiểm tra format để tránh path traversal
        if not re.match(r"^\d{8}-\d{6}-[A-Za-z0-9_\-]+$", last_batch):
            last_batch = None
        else:
            d = Path(settings.MEDIA_ROOT) / "labels" / last_batch
            if not d.is_dir():
                last_batch = None

    return render(
        request,
        "inventory/generate.html",
        {
            "form": form,
            "products": products,
            "last_batch": last_batch,        # để template show nút tải
            "media_url": settings.MEDIA_URL, # để mở thư mục
        },
    )


def download_batch(request, batch: str):
    """
    Nén MEDIA_ROOT/labels/<batch> thành file .zip và trả về.
    batch phải có dạng YYYYMMDD-HHMMSS-SKU
    """
    if not re.match(r"^\d{8}-\d{6}-[A-Za-z0-9_\-]+$", batch or ""):
        return HttpResponseBadRequest("Bad batch name.")

    dir_path = Path(settings.MEDIA_ROOT) / "labels" / batch
    if not dir_path.is_dir():
        raise Http404("Batch not found.")

    # Nén vào bộ nhớ (phù hợp số lượng tem vừa phải)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        files = sorted(dir_path.glob("*.png"))
        for fp in files:
            zf.write(fp, arcname=fp.name)
        zf.writestr(
            "MANIFEST.txt",
            f"Batch: {batch}\nGenerated at: {timezone.now():%Y-%m-%d %H:%M:%S}\nFiles: {len(files)}\n"
        )

    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{batch}.zip"'
    return resp


# ---------- Scan & Move ----------
@transaction.atomic
# def scan_move(request):
#     if request.method == "POST":
#         form = ScanMoveForm(request.POST)
#         if form.is_valid():
#             action = form.cleaned_data["action"]
#             code = form.cleaned_data["barcode"].strip()
#             fwh = form.cleaned_data["from_wh"]
#             twh = form.cleaned_data["to_wh"]

#             # Ghi nhớ lựa chọn để lần sau mở trang vẫn giữ
#             request.session["scan_action"] = action
#             request.session["scan_to_wh_id"] = twh.id if twh else None

#             try:
#                 item = (
#                     Item.objects.select_for_update()
#                     .select_related("product", "warehouse")
#                     .get(barcode_text=code)
#                 )
#             except Item.DoesNotExist:
#                 messages.error(request, f"Không tìm thấy barcode: {code}")
#                 return redirect("scan_move")

#             # ---- IDMP: bảo toàn số liệu, không cộng trừ trùng lặp ----
#             if action == "IN":
#                 if not twh:
#                     messages.error(request, "IN cần chọn 'To kho'.")
#                     return redirect("scan_move")

#                 if item.warehouse_id:
#                     if item.warehouse_id == twh.id:
#                         messages.warning(
#                             request, f"{code} đã nằm trong kho {twh.code}. Bỏ qua."
#                         )
#                     else:
#                         messages.warning(
#                             request,
#                             f"{code} đang ở {item.warehouse.code}. Dùng TRANSFER để chuyển sang {twh.code}.",
#                         )
#                     return redirect("scan_move")

#                 # Hợp lệ: chưa ở kho nào → IN lần đầu
#                 Move.objects.create(item=item, action="IN", to_wh=twh, note="IN (scan)")
#                 item.warehouse = twh
#                 item.status = "in_stock"
#                 item.save(update_fields=["warehouse", "status"])
#                 adjust_inventory(item.product, twh, +1)
#                 messages.success(request, f"IN {code} → {twh.code}")
#                 return redirect("scan_move")

#             elif action == "OUT":
#                 if not item.warehouse_id:
#                     messages.warning(
#                         request, f"{code} đã OUT trước đó (không ở kho nào). Bỏ qua."
#                     )
#                     return redirect("scan_move")

#                 Move.objects.create(
#                     item=item, action="OUT", from_wh=item.warehouse, note="OUT (scan)"
#                 )
#                 adjust_inventory(item.product, item.warehouse, -1)
#                 item.warehouse = None
#                 item.status = "shipped"
#                 item.save(update_fields=["warehouse", "status"])
#                 messages.success(request, f"OUT {code}")
#                 return redirect("scan_move")

#             else:  # TRANSFER
#                 if not (fwh and twh):
#                     messages.error(request, "TRANSFER cần chọn cả 'From kho' và 'To kho'.")
#                     return redirect("scan_move")

#                 if item.warehouse_id != fwh.id:
#                     current_wh = item.warehouse.code if item.warehouse_id else "không ở kho nào"
#                     messages.warning(
#                         request,
#                         f"{code} đang ở {current_wh}. 'From kho' không khớp → bỏ qua.",
#                     )
#                     return redirect("scan_move")

#                 Move.objects.create(
#                     item=item,
#                     action="TRANSFER",
#                     from_wh=fwh,
#                     to_wh=twh,
#                     note="TRANSFER (scan)",
#                 )
#                 adjust_inventory(item.product, fwh, -1)
#                 adjust_inventory(item.product, twh, +1)
#                 item.warehouse = twh
#                 item.save(update_fields=["warehouse"])
#                 messages.success(request, f"TRANSFER {code}: {fwh.code} → {twh.code}")
#                 return redirect("scan_move")
#     else:
#         # Khởi tạo mặc định theo session lần trước
#         init = {"action": request.session.get("scan_action", "IN")}
#         to_id = request.session.get("scan_to_wh_id")
#         if to_id:
#             init["to_wh"] = Warehouse.objects.filter(id=to_id).first()
#         form = ScanMoveForm(initial=init)

#     return render(request, "inventory/scan_move.html", {"form": form})


def scan_move(request):
    if request.method == "POST":
        form = ScanMoveForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            code   = form.cleaned_data["barcode"].strip()
            fwh    = form.cleaned_data["from_wh"]
            twh    = form.cleaned_data["to_wh"]

            # nhớ lựa chọn cho lần sau
            request.session["scan_action"] = action
            if twh: request.session["scan_to_wh_id"]   = twh.id
            if fwh: request.session["scan_from_wh_id"] = fwh.id

            try:
                item = (Item.objects.select_for_update()
                        .select_related("product","warehouse")
                        .get(barcode_text=code))
            except Item.DoesNotExist:
                messages.error(request, f"Không tìm thấy barcode: {code}")
                return redirect("scan_move")

            if action == "IN":
                if not twh:
                    messages.error(request, "IN cần chọn 'To kho'.")
                    return redirect("scan_move")

                if item.warehouse:
                    if item.warehouse == twh:
                        messages.warning(request, f"{code} đã ở {twh.code}. Bỏ qua.")
                    else:
                        messages.warning(request, f"{code} đang ở {item.warehouse.code}. Hãy dùng TRANSFER.")
                    return redirect("scan_move")

                Move.objects.create(item=item, action="IN", to_wh=twh, note="IN (scan)")
                item.warehouse = twh; item.status = "in_stock"
                item.save(update_fields=["warehouse","status"])
                adjust_inventory(item.product, twh, +1)
                messages.success(request, f"IN {code} → {twh.code}")
                return redirect("scan_move")

            elif action == "OUT":
                if not item.warehouse:
                    messages.warning(request, f"{code} đã OUT trước đó. Bỏ qua.")
                    return redirect("scan_move")

                Move.objects.create(item=item, action="OUT", from_wh=item.warehouse, note="OUT (scan)")
                adjust_inventory(item.product, item.warehouse, -1)
                item.warehouse = None; item.status = "shipped"
                item.save(update_fields=["warehouse","status"])
                messages.success(request, f"OUT {code}")
                return redirect("scan_move")

            else:  # TRANSFER
                if not twh:
                    messages.error(request, "TRANSFER cần chọn 'To kho'.")
                    return redirect("scan_move")

                # >>> Mới: nếu bỏ trống From → tự dùng kho hiện tại của mã
                if not fwh:
                    fwh = item.warehouse

                if not fwh:
                    messages.warning(request, f"{code} đang không ở kho nào → không thể TRANSFER. Hãy IN trước.")
                    return redirect("scan_move")

                if item.warehouse != fwh:
                    current_wh = item.warehouse.code if item.warehouse else "không ở kho nào"
                    messages.warning(request, f"{code} đang ở {current_wh}. 'From kho' không khớp → bỏ qua.")
                    return redirect("scan_move")

                Move.objects.create(item=item, action="TRANSFER", from_wh=fwh, to_wh=twh, note="TRANSFER (scan)")
                adjust_inventory(item.product, fwh, -1)
                adjust_inventory(item.product, twh, +1)
                item.warehouse = twh
                item.save(update_fields=["warehouse"])
                messages.success(request, f"TRANSFER {code}: {fwh.code} → {twh.code}")
                return redirect("scan_move")
    else:
        # Khởi tạo form với các lựa chọn đã nhớ
        init = {"action": request.session.get("scan_action","IN")}
        to_id   = request.session.get("scan_to_wh_id")
        from_id = request.session.get("scan_from_wh_id")
        if to_id:
            init["to_wh"] = Warehouse.objects.filter(id=to_id).first()
        if from_id:
            init["from_wh"] = Warehouse.objects.filter(id=from_id).first()
        form = ScanMoveForm(initial=init)

    return render(request, "inventory/scan_move.html", {"form": form})

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
    return render(request, "inventory/barcode_lookup.html", {"item": item, "moves": moves})


# ---------- CRUD Product ----------
def product_list(request):
    q = request.GET.get("q", "").strip()
    qs = Product.objects.all().order_by("sku")
    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(name__icontains=q))
    from django.core.paginator import Paginator

    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "inventory/product_list.html", {"page_obj": page_obj, "q": q})


def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã tạo sản phẩm.")
            return redirect("product_list")
    else:
        form = ProductForm()
    return render(
        request, "inventory/product_form.html", {"form": form, "title": "Tạo sản phẩm"}
    )


def product_update(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật.")
            return redirect("product_list")
    else:
        form = ProductForm(instance=obj)
    return render(
        request, "inventory/product_form.html", {"form": form, "title": f"Sửa: {obj.sku}"}
    )


def product_delete(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Đã xoá.")
        return redirect("product_list")
    return render(request, "inventory/product_confirm_delete.html", {"obj": obj})


# ---------- Query Panel ----------
def _execute_sql(sql: str):
    """
    Cho phép chạy SELECT/INSERT/UPDATE/DELETE/PRAGMA... có kiểm soát:
    chỉ chấp nhận khi từ đầu tiên thuộc whitelist.
    """
    allowed = (
        "select",
        "with",
        "insert",
        "update",
        "delete",
        "replace",
        "pragma",
        "begin",
        "commit",
        "rollback",
    )
    if not re.match(r"^\s*(" + "|".join(allowed) + r")\b", sql, flags=re.IGNORECASE | re.DOTALL):
        raise ValueError("Chỉ cho phép: " + ", ".join(allowed))

    with connection.cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall() if cur.description else []
    return cols, rows



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

def _execute_select_sql(sql: str):
    """Chỉ cho phép SELECT để an toàn."""
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Chỉ cho phép SELECT.")
    with connection.cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
    return cols, rows

def query_panel(request):
    tables = _list_db_tables_with_type()
    table_names = [t["name"] for t in tables]

    selected = request.GET.get("table")
    if selected not in table_names:
        selected = table_names[0] if table_names else None

    # Clear query -> về mẫu
    if request.GET.get("clear") == "1":
        return redirect(f"{request.path}?table={selected}" if selected else request.path)

    # SQL mặc định: preview bảng đang chọn
    if request.method == "POST":
        sql_text = request.POST.get("sql", "").strip()
    else:
        sql_text = f"SELECT * FROM {selected} LIMIT 100" if selected else ""

    # Lấy danh sách cột của bảng đang xem (nếu có)
    columns = None
    if selected:
        try:
            with connection.cursor() as cur:
                desc = connection.introspection.get_table_description(cur, selected)
                columns = [d.name for d in desc]
        except Exception:
            columns = None

    # Chạy query
    result = None
    error = None
    rows_count = None
    status_text = None

    if request.method == "POST":
        try:
            cols, rows = _execute_select_sql(sql_text)
            result = {"cols": cols, "rows": rows}
            rows_count = len(rows)
            status_text = f"Query executed successfully. {rows_count} rows returned."
            messages.success(request, status_text)
        except Exception as e:
            error = str(e)
    else:
        # GET: tự preview
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
        "status_text": status_text,
    }
    return render(request, "inventory/query_panel.html", ctx)