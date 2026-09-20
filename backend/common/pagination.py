"""목록 응답은 DRF 페이지네이션 래퍼를 따른다 (specs/15 §1)."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
