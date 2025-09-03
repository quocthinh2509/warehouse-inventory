# inventory/pagination.py
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class PageLimitPagination(PageNumberPagination):
    page_query_param = "page"
    page_size_query_param = "limit"   # dùng ?limit=
    page_size = 20
    max_page_size = 1000

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "page": self.page.number,
            "page_size": self.get_page_size(self.request),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })
