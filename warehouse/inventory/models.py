import zlib
from django.db import models, transaction

from django.db.models import Max
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

# 1) Danh mục hàng hoá
class Product(models.Model):
    sku   = models.CharField(max_length=64, unique=True, db_index=True)
    name  = models.CharField(max_length=255)
    code4 = models.CharField(
        max_length=4,
        unique=True,
        validators=[RegexValidator(r'^\d{4}$', 'Mã sản phẩm phải gồm đúng 4 chữ số.')],
        editable=False,  # không cho sửa trên form/admin
    )

    class Meta:
        ordering = ["id"]

    @staticmethod
    def _gen_code4_from_sku(sku: str, qs) -> str:
        """
        Sinh code4 ổn định từ SKU bằng CRC32; nếu trùng thì +1 (mod 10000) đến khi trống.
        qs: truyền vào Product.objects (để test dễ & tránh vòng import)
        """
        base = zlib.crc32(sku.encode("utf-8")) % 10000
        for step in range(10000):
            candidate = f"{(base + step) % 10000:04d}"
            if not qs.filter(code4=candidate).exists():
                return candidate
        raise RuntimeError("Không còn code4 trống.")

    def save(self, *args, **kwargs):
        # tạo mới: chỉ nhập sku + name → tự sinh code4
        if not self.pk:
            if not self.sku:
                raise ValueError("SKU là bắt buộc.")
            self.code4 = Product._gen_code4_from_sku(self.sku, type(self).objects)
        # sửa: cho phép đổi sku/name; code4 giữ nguyên để không vỡ barcode đã in
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code4} - {self.sku} - {self.name}"


# 2) Danh mục kho
class Warehouse(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.code


# 3) Từng đơn vị hàng (mỗi cái 1 barcode)
class Item(models.Model):
    product      = models.ForeignKey("inventory.Product", on_delete=models.PROTECT)
    import_date  = models.DateField(default=timezone.localdate)  # ngày nhập (ddmmyy)
    seq          = models.PositiveIntegerField(null=True, blank=True)  # sẽ auto-gen
    barcode_text = models.CharField(max_length=15, unique=True, db_index=True)  # 4+6+5
    warehouse    = models.ForeignKey("inventory.Warehouse", null=True, blank=True, on_delete=models.PROTECT)
    status       = models.CharField(max_length=32, default="none")
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        # Không trùng số thứ tự trong cùng (product, import_date)
        unique_together = (("product", "import_date", "seq"),)
        indexes = [
            models.Index(fields=["product", "import_date"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.barcode_text

    def _compose_barcode(self) -> str:
        date6 = self.import_date.strftime("%d%m%y")
        return f"{self.product.code4}{date6}{self.seq:05d}"

    def save(self, *args, **kwargs):
        """
        - Nếu chưa có seq => tự sinh seq tiếp theo cho (product, import_date).
        - Luôn cập nhật barcode_text theo (code4 + ddmmyy + seq5).
        - Dùng SELECT ... FOR UPDATE để chống đụng độ khi tạo đồng thời.
        """
        if self.import_date is None:
            self.import_date = timezone.localdate()

        with transaction.atomic():
            if not self.seq:
                # Khoá dải dữ liệu liên quan để tính seq an toàn
                current_max = (
                    Item.objects
                    .select_for_update()
                    .filter(product=self.product, import_date=self.import_date)
                    .aggregate(m=Max("seq"))["m"] or 0
                )
                self.seq = current_max + 1

            # Lắp barcode theo quy tắc 4+6+5
            self.barcode_text = self._compose_barcode()
            super().save(*args, **kwargs)

# 4) Tồn kho tổng hợp theo kho
class Inventory(models.Model):
    product   = models.ForeignKey(Product, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    qty       = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "warehouse"], name="uniq_product_warehouse"),
        ]

    def __str__(self):
        return f"{self.product.code4} @ {self.warehouse.code}: {self.qty}"
    
    @staticmethod
    def adjust(product, warehouse, delta: int):
        """Điều chỉnh tồn kho (cho phép âm logic, lưu không âm).

        Ghi chú: Không raise khi new_qty < 0 để không chặn nghiệp vụ OUT.
        Lượng tồn lưu trong bảng sẽ được chặn về 0 (không âm) để an toàn.
        """
        inv, _ = Inventory.objects.select_for_update().get_or_create(
            product=product, warehouse=warehouse, defaults={"qty": 0}
        )
        new_qty = (inv.qty or 0) + int(delta or 0)
        # Cho phép ghi nhận OUT vượt tồn, nhưng không lưu âm vào cột qty
        inv.qty = new_qty if new_qty >= 0 else 0
        inv.save(update_fields=["qty"])





# 5) Log di chuyển (IN/OUT) — hỗ trợ cả 'itemized' lẫn 'bulk'
class Move(models.Model):
    ACTIONS = (("IN", "IN"), ("OUT", "OUT"))

    # --- Chế độ 1: theo Item (qty ngầm định = 1) ---
    item   = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE, related_name="moves")

    # --- Chế độ 2: theo Bulk (không item) ---
    product  = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(null=True, blank=True)

    action      = models.CharField(max_length=10, choices=ACTIONS)
    type_action = models.CharField(max_length=64, blank=True, default="")
    from_wh     = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_from")
    to_wh       = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_to")
    note        = models.CharField(max_length=255, blank=True, default="")
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    # ✨ Thêm sẵn các trường meta/batch
    tag            = models.PositiveIntegerField(default=1, db_index=True)
    created_by     = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    batch_id       = models.CharField(max_length=32, blank=True, db_index=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at", "action"]),
            models.Index(fields=["tag", "created_at"]),
            models.Index(fields=["batch_id"]),
        ]

    def __str__(self):
        if self.item:
            return f"{self.action} ITEM {self.item.barcode_text}"
        return f"{self.action} BULK {self.product.code4} x{self.quantity}"

    # --- Ràng buộc hợp lệ ---
    def clean(self):
        super().clean()
        has_item = self.item is not None
        has_bulk = self.product is not None or self.quantity is not None

        if has_item and has_bulk:
            raise ValidationError("Move phải là 'theo Item' HOẶC 'theo Bulk' (không được cả hai).")

        if not has_item and not has_bulk:
            raise ValidationError("Move thiếu dữ liệu: cần Item hoặc Product+Quantity.")

        if not has_item and (self.product is None or not self.quantity):
            raise ValidationError("Bulk cần đủ (product, quantity>0).")

        # Kiểm tra from/to theo action
        if self.action == "IN" and not self.to_wh:
            raise ValidationError("IN cần to_wh (kho nhận).")
        if self.action == "OUT" and not self.from_wh:
            raise ValidationError("OUT cần from_wh (kho xuất).")

        # Nếu theo Item, suy ra product từ item
        if has_item:
            if self.action == "IN" and self.to_wh is None:
                raise ValidationError("IN item cần to_wh.")
            if self.action == "OUT" and self.from_wh is None:
                raise ValidationError("OUT item cần from_wh.")

    # --- Áp dụng & cập nhật Inventory an toàn ---
    def apply(self):
        """
        Gọi sau khi save() để cập nhật tồn kho.
        Dùng trong transaction & select_for_update ở nơi gọi batch để tránh race.
        """
        if self.item:
            product = self.item.product
            qty = 1
        else:
            product = self.product
            qty = int(self.quantity or 0)

        if self.action == "IN":
            # Bulk: tăng tồn kho to_wh
            # Itemized: gán warehouse cho item (nếu muốn), tăng tồn kho
            if self.item and self.to_wh:
                self.item.warehouse = self.to_wh
                self.item.status = "in_stock"
                self.item.save(update_fields=["warehouse", "status"])
            Inventory.adjust(product, self.to_wh, +qty)

        elif self.action == "OUT":
            # Bulk: trừ tồn kho from_wh
            # Itemized: clear warehouse/item status nếu muốn
            Inventory.adjust(product, self.from_wh, -qty)
            if self.item and self.from_wh:
                self.item.warehouse = None
                self.item.status = "shipping"
                self.item.save(update_fields=["warehouse", "status"])


# 6) Đơn nhập/xuất để nhập tay, đọc file, hoặc API
class StockOrder(models.Model):
    ORDER_TYPES = (("IN", "IN"), ("OUT", "OUT"))
    SOURCES     = (("MANUAL", "MANUAL"), ("SHEET", "SHEET"), ("API", "API"))

    order_type   = models.CharField(max_length=3, choices=ORDER_TYPES)
    source       = models.CharField(max_length=10, choices=SOURCES, default="MANUAL")
    reference    = models.CharField(max_length=64, blank=True, default="")  # mã đơn, số chứng từ
    external_id  = models.CharField(max_length=64, null=True, blank=True, unique=True, db_index=True)  # id ngoài để idempotent
    note         = models.CharField(max_length=255, blank=True, default="")
    created_by   = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_at   = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)

    # nơi đi/đến mặc định của cả đơn (dùng cho bulk)
    from_wh = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="orders_from")
    to_wh   = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="orders_to")

    def __str__(self):
        return f"{self.order_type}#{self.id} ({self.source})"

    def confirm(self, batch_id: str = ""):
        """
        Xác nhận đơn: sinh Move tương ứng cho từng dòng.
        - Nếu dòng có item_ids: tạo Move theo item (qty=1 từng item)
        - Nếu dòng chỉ có product+quantity: tạo Move bulk
        """
        if self.is_confirmed:
            return

        with transaction.atomic():
            for line in self.lines.select_for_update().all():
                if line.item:
                    # itemized
                    mv = Move.objects.create(
                        item=line.item,
                        action=self.order_type,
                        from_wh=self.from_wh if self.order_type == "OUT" else None,
                        to_wh=self.to_wh   if self.order_type == "IN"  else None,
                        type_action=self.source,
                        note=self.note,
                        created_by=self.created_by,
                        batch_id=batch_id or f"ORDER-{self.id}",
                    )
                    mv.apply()
                else:
                    # bulk
                    if not line.product or not line.quantity:
                        raise ValidationError("Dòng đơn bulk thiếu product/quantity.")
                    mv = Move.objects.create(
                        product=line.product,
                        quantity=line.quantity,
                        action=self.order_type,
                        from_wh=self.from_wh if self.order_type == "OUT" else None,
                        to_wh=self.to_wh   if self.order_type == "IN"  else None,
                        type_action=self.source,
                        note=self.note,
                        created_by=self.created_by,
                        batch_id=batch_id or f"ORDER-{self.id}",
                    )
                    mv.apply()

            self.is_confirmed = True
            self.confirmed_at = timezone.now()
            self.save(update_fields=["is_confirmed", "confirmed_at"])


class StockOrderLine(models.Model):
    order    = models.ForeignKey(StockOrder, on_delete=models.CASCADE, related_name="lines")
    # Chọn 1 trong 2:
    item     = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT)     # cho case có barcode (qty ngầm =1)
    product  = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT)  # cho bulk
    quantity = models.PositiveIntegerField(null=True, blank=True)                           # cho bulk

    note     = models.CharField(max_length=255, blank=True, default="")

    def clean(self):
        super().clean()
        if self.item and (self.product or self.quantity):
            raise ValidationError("Một dòng chỉ được chọn Item hoặc Product+Quantity.")
        if not self.item and not (self.product and self.quantity):
            raise ValidationError("Dòng thiếu dữ liệu: cần Item hoặc Product+Quantity.")


# (tuỳ chọn) Lưu câu query SQL cho dashboard
class SavedQuery(models.Model):
    name = models.CharField(max_length=128)
    sql  = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

