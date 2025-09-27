# erp_the20/urls/ui_urls.py
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    # Trang chấm công (UI checkin/checkout)
    path(
        "",
        TemplateView.as_view(template_name="erp_the20/index.html"),
        name="ui-attendance-home",
    ),
    # Trang xem bảng tổng hợp công
    path(
        "summaries/",
        TemplateView.as_view(template_name="erp_the20/summaries.html"),
        name="ui-attendance-summaries",
    ),
]
