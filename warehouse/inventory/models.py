from django.db import models
from django.core.validators import RegexValidator

# 1) Danh mục hàng hoá
class Product(models.Model):
    sku   = models.CharField(max_length=64, unique=True)
    name  = models.CharField(max_length=255)
    # Mã số 4 chữ số dùng để gen barcode (bắt buộc là số)
    code4 = models.CharField(
        max_length=4,
        unique=True,
        validators=[RegexValidator(r'^\d{4}$', 'Mã sản phẩm phải gồm đúng 4 chữ số.')]
    )

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
    product      = models.ForeignKey(Product, on_delete=models.PROTECT)
    # thông tin lô nhập để build barcode
    import_date  = models.DateField()                   # ngày nhập (để gen ddMMyy)
    batch_no     = models.PositiveIntegerField()        # đợt nhập trong ngày (01..99)
    seq          = models.PositiveIntegerField()        # số thứ tự (reset theo product+date+batch)
    barcode_text = models.CharField(max_length=32, unique=True, db_index=True)  # toàn số
    warehouse    = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT)
    status       = models.CharField(max_length=32, default="in_stock")
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        # đảm bảo không trùng số thứ tự trong cùng (product, date, batch)
        constraints = [
            models.UniqueConstraint(
                fields=["product", "import_date", "batch_no", "seq"],
                name="uniq_prod_date_batch_seq",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "import_date", "batch_no"]),
        ]

    def __str__(self):
        return self.barcode_text


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
    type_action = models.CharField(max_length=64, blank=True, default="")  # ví dụ: "batch-01", "ban-le", "kiem-ke", ...
    from_wh     = models.ForeignKey(
        Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_from"
    )
    to_wh       = models.ForeignKey(
        Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_to"
    )
    note        = models.CharField(max_length=255, blank=True, default="")
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

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


# from django.db import models

# # 1) Danh mục hàng hoá
# class Product(models.Model):
#     sku  = models.CharField(max_length=64, unique=True)
#     name = models.CharField(max_length=255)

#     def __str__(self):
#         return f"{self.sku} - {self.name}"


# # 2) Danh mục kho
# class Warehouse(models.Model):
#     code = models.CharField(max_length=32, unique=True)
#     name = models.CharField(max_length=128)

#     def __str__(self):
#         return self.code


# # 3) Từng đơn vị hàng (mỗi cái 1 barcode)
# class Item(models.Model):
#     product      = models.ForeignKey(Product, on_delete=models.PROTECT)
#     seq          = models.PositiveIntegerField()                           # số thứ tự trong SKU
#     barcode_text = models.CharField(max_length=128, unique=True, db_index=True)  # ví dụ: NX-100ML-000001
#     warehouse    = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT)
#     status       = models.CharField(max_length=32, default="in_stock")     # in_stock/shipped/...
#     created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(fields=["product", "seq"], name="uniq_product_seq"),
#         ]

#     def __str__(self):
#         return self.barcode_text


# # 4) Tồn kho tại mỗi kho (bảng tổng hợp)
# class Inventory(models.Model):
#     product   = models.ForeignKey(Product, on_delete=models.PROTECT)
#     warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
#     qty       = models.PositiveIntegerField(default=0)

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(fields=["product", "warehouse"], name="uniq_product_warehouse"),
#         ]

#     def __str__(self):
#         return f"{self.product.sku} @ {self.warehouse.code}: {self.qty}"


# # 5) Log di chuyển (chỉ IN/OUT) + type_action
# class Move(models.Model):
#     ACTIONS = (("IN", "IN"), ("OUT", "OUT"))
#     item        = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="moves")
#     action      = models.CharField(max_length=10, choices=ACTIONS)
#     type_action = models.CharField(max_length=64, blank=True, default="")  # ví dụ: nhập lô, bán lẻ, kiểm kê, v.v.
#     from_wh     = models.ForeignKey(
#         Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_from"
#     )
#     to_wh       = models.ForeignKey(
#         Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_to"
#     )
#     note        = models.CharField(max_length=255, blank=True, default="")
#     created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

#     class Meta:
#         ordering = ["-created_at"]

#     def __str__(self):
#         return f"{self.action} {self.item.barcode_text}"
        

# # (tuỳ chọn) Lưu câu query SQL trên dashboard
# class SavedQuery(models.Model):
#     name = models.CharField(max_length=128)
#     sql  = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return self.name
