from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from erp_the20.serializers.notification_serializer import NotificationSerializer
from erp_the20.services import notification_service as svc
from erp_the20.selectors.notification_selector import notifications_for_user, notifications_search

class NotificationViewSet(viewsets.ViewSet):
    # GET /the20/notifications/?user_id=123
    def list(self, request):
        user_id = request.query_params.get("user_id")
        if user_id:
            qs = notifications_for_user(int(user_id))
        else:
            qs = notifications_search()
        return Response(NotificationSerializer(qs, many=True).data)

    # POST /the20/notifications/send   (gửi in-app + email + lark)
    @action(detail=False, methods=["post"])
    def send(self, request):
        data = request.data

        # NEW: parse boolean (mặc định False)
        def _to_bool(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("1","true","yes","y","on")
            if isinstance(v, (int, float)):
                return bool(v)
            return False

        send_email = _to_bool(data.get("send_email", False))
        send_lark  = _to_bool(data.get("send_lark", False))

        obj = svc.send_broadcast_inapp_email_lark(
            title=data["title"],
            recipients=data.get("recipients"),
            to_user=data.get("to_user"),
            payload=data.get("payload"),
            object_type=data.get("object_type",""),
            object_id=data.get("object_id",""),
            send_email=send_email,
            send_lark=send_lark,
            email_subject=data.get("email_subject"),
            email_text=data.get("email_text"),
            email_html=data.get("email_html"),
            lark_text=data.get("lark_text"),
        )
        return Response(NotificationSerializer(obj).data, status=status.HTTP_201_CREATED)
