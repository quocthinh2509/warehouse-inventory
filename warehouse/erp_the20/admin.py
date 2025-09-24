from django.contrib import admin
from .models import WifiVerifier

@admin.register(WifiVerifier)
class WifiVerifierAdmin(admin.ModelAdmin):
    list_display = ("verifier_id", "is_active")
    search_fields = ("verifier_id",)

# Register your models here.
