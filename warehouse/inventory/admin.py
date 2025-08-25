from django.contrib import admin
from .models import Product, Warehouse, Item, Inventory, Move

admin.site.register(Product)
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
