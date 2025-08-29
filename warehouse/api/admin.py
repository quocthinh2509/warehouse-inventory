from django.contrib import admin
from .models import Product, Warehouse, Item, Inventory, Move, StockOrder, StockOrderLine, SavedQuery

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "code4", "sku", "name")
    search_fields = ("sku", "name", "code4")
    ordering = ("id",)

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    search_fields = ("code", "name")

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("id", "barcode_text", "product", "import_date", "seq", "warehouse", "status", "created_at")
    list_filter = ("status", "import_date", "warehouse")
    search_fields = ("barcode_text", "product__sku", "product__code4")

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "warehouse", "qty")
    list_filter = ("warehouse",)
    search_fields = ("product__sku", "product__code4", "warehouse__code")

@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "item", "product", "quantity", "from_wh", "to_wh", "created_by", "batch_id", "created_at")
    list_filter = ("action", "from_wh", "to_wh", "created_at")
    search_fields = ("item__barcode_text", "product__sku", "batch_id", "note")

class StockOrderLineInline(admin.TabularInline):
    model = StockOrderLine
    extra = 0

@admin.register(StockOrder)
class StockOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "order_type", "source", "reference", "from_wh", "to_wh", "is_confirmed", "created_at", "confirmed_at")
    list_filter = ("order_type", "source", "is_confirmed", "created_at")
    search_fields = ("reference", "note")
    inlines = [StockOrderLineInline]

@admin.register(SavedQuery)
class SavedQueryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)
