# -*- coding: utf-8 -*-
from rest_framework.pagination import PageNumberPagination

class DefaultPagination(PageNumberPagination):
    page_size = 20                # mặc định
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 200
