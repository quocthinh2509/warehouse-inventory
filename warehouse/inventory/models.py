import zlib
from django.db import models, transaction

from django.db.models import Max
from django.utils import timezone
from django.core.validators import RegexValidator

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
    status       = models.CharField(max_length=32, default="in_stock")
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


# 5) Log di chuyển (chỉ IN/OUT) + type_action
class Move(models.Model):
    ACTIONS = (("IN", "IN"), ("OUT", "OUT"))
    item        = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="moves")
    action      = models.CharField(max_length=10, choices=ACTIONS)
    type_action = models.CharField(max_length=64, blank=True, default="")
    from_wh     = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_from")
    to_wh       = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_to")
    note        = models.CharField(max_length=255, blank=True, default="")
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    # ✨ THÊM MỚI:
    tag         = models.PositiveIntegerField(default=1, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.item.barcode_text}"


# (tuỳ chọn) Lưu câu query SQL cho dashboard
class SavedQuery(models.Model):
    name = models.CharField(max_length=128)
    sql  = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


