from django.contrib import admin
from .models import AllowedIP, Attendance

@admin.register(AllowedIP)
class AllowedIPAdmin(admin.ModelAdmin):
    list_display = ('ip', 'note', 'updated_at')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('created_at','user_id','action','ip_from_client','ip_from_request','allowed')
    list_filter = ('allowed','action')
