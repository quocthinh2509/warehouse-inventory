from django.db import models

# 1) Danh mục hàng hoá
class Product(models.Model):
    sku  = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    def __str__(self): return f"{self.sku} - {self.name}"

# Danh mục kho (để lưu tồn theo kho)
class Warehouse(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    def __str__(self): return self.code

# 2) Từng đơn vị hàng (mỗi cái 1 barcode)
class Item(models.Model):
    product      = models.ForeignKey(Product, on_delete=models.PROTECT)
    seq          = models.PositiveIntegerField()                   # số thứ tự trong SKU
    barcode_text = models.CharField(max_length=128, unique=True)   # VD: NX-100ML-000001
    warehouse    = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT)
    status       = models.CharField(max_length=32, default="in_stock")  # in_stock/shipped/...
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product","seq"], name="uniq_product_seq"),
        ]
    def __str__(self): return self.barcode_text

# 3) Tồn kho tại mỗi kho (bảng tổng hợp)
class Inventory(models.Model):
    product   = models.ForeignKey(Product, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    qty       = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product","warehouse"], name="uniq_product_warehouse")
        ]

# 4) Log di chuyển hàng ra/vào/transfer
class Move(models.Model):
    ACTIONS = (("IN","IN"),("OUT","OUT"),("TRANSFER","TRANSFER"),("REPRINT","REPRINT"),("RELABEL","RELABEL"))
    item      = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="moves")
    action    = models.CharField(max_length=10, choices=ACTIONS)
    from_wh   = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_from")
    to_wh     = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="moves_to")
    note      = models.CharField(max_length=255, blank=True, default="")
    created_at= models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
class SavedQuery(models.Model):
    name = models.CharField(max_length=128)
    sql  = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
