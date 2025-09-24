import json
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import AllowedIP, Attendance
from django.shortcuts import render
def _get_request_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    ip = request.META.get('REMOTE_ADDR')
    if ip and ip.startswith('::ffff:'):
        ip = ip.replace('::ffff:', '')
    return ip

@csrf_exempt
def set_allowed_ip(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    token = request.META.get('HTTP_X_MAC_TOKEN')
    if not token or token != settings.MAC_SECRET_TOKEN:
        return HttpResponseForbidden(json.dumps({'ok': False, 'error': 'Invalid token'}), content_type='application/json')

    try:
        data = json.loads(request.body.decode('utf-8'))
        ip = data.get('ip')
        note = data.get('note','')
        if not ip:
            return HttpResponseBadRequest(json.dumps({'ok': False, 'error': 'Missing ip'}), content_type='application/json')
        obj, created = AllowedIP.objects.update_or_create(ip=ip, defaults={'note': note})
        return JsonResponse({'ok': True, 'ip': ip, 'created': created})
    except Exception as e:
        return HttpResponseBadRequest(json.dumps({'ok': False, 'error': str(e)}), content_type='application/json')

def attendance_page(request):
    return render(request, "attendance.html")

@csrf_exempt
def attendance_api(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body)
    except:
        data = {}

    user_id = data.get('userId') or 'unknown'
    action = data.get('action') or 'checkin'
    ip_from_client = data.get('ip')
    ip_from_request = _get_request_ip(request)

    allowed = AllowedIP.objects.filter(ip=ip_from_request).exists()

    log = Attendance.objects.create(
        user_id=user_id,
        action=action,
        ip_from_client=ip_from_client,
        ip_from_request=ip_from_request,
        allowed=allowed
    )

    if not allowed:
        return JsonResponse({'ok': False, 'allowed': False, 'message': 'Không ở trong mạng công ty'}, status=403)

    return JsonResponse({'ok': True, 'allowed': True, 'attendance_id': log.id})


def attendance_page(request):
    return render(request, "attendance/attendance.html")