from erp_the20.models import Notification

def send(to_user, title: str, body: str, payload=None, channel="inapp"):
    Notification.objects.create(to_user=to_user, channel=channel, title=title, body=body, payload=payload or {})