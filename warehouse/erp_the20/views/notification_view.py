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
    # body:
    # {
    #   "title": "Thông báo",
    #   "recipients": [1,2], "to_user": 7,
    #   "payload": {"body":"Nội dung..."},
    #   "object_type": "general", "object_id": "123",
    #   "email_subject": "...", "email_text": "...", "email_html": "<b>...</b>",
    #   "lark_text": "..."
    # }
    @action(detail=False, methods=["post"])
    def send(self, request):
        data = request.data
        obj = svc.send_broadcast_inapp_email_lark(
            title=data["title"],
            recipients=data.get("recipients"),
            to_user=data.get("to_user"),
            payload=data.get("payload"),
            object_type=data.get("object_type",""),
            object_id=data.get("object_id",""),
            email_subject=data.get("email_subject"),
            email_text=data.get("email_text"),
            email_html=data.get("email_html"),
            lark_text=data.get("lark_text"),
        )
        return Response(NotificationSerializer(obj).data, status=status.HTTP_201_CREATED)
