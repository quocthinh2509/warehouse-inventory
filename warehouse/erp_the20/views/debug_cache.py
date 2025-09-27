# erp_the20/views/debug_cache.py
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(require_GET, name="dispatch")
class DebugTokensView(View):
    """
    Endpoint nội bộ để liệt kê các token hiện có trong cache.
    ⚠️ Nên bảo vệ bằng quyền admin hoặc IP whitelist.
    """
    def get(self, request):
        try:
            # Chỉ hoạt động nếu cache backend hỗ trợ .keys (vd Redis)
            keys = cache.keys("local_token:*")
            tokens = [k.replace("local_token:", "") for k in keys]
            return JsonResponse({"tokens": tokens})
        except Exception as e:
            return JsonResponse(
                {"error": "cache_backend_no_keys", "detail": str(e)},
                status=500
            )
