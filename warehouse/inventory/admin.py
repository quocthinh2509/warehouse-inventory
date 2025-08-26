from django.contrib import admin
from .models import Product, Warehouse, Item, Inventory, Move

# Đăng ký các model đơn giản
admin.site.register(Warehouse)
admin.site.register(Inventory)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("barcode_text","product","seq","warehouse","status","created_at")
    search_fields = ("barcode_text","product__sku","product__name")
    list_filter = ("warehouse","status")

@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("item","action","from_wh","to_wh","created_at","note")
    list_filter = ("action","from_wh","to_wh")
    search_fields = ("item__barcode_text",)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "sku", "name", "code4")
    search_fields = ("sku", "name", "code4")
    readonly_fields = ("code4",)  # code4 chỉ đọc
    ordering = ("id",)
    fields = ("sku", "name", "code4")  # code4 hiển thị read-only
