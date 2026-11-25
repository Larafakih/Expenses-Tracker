from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 10                   
    page_query_param = "pagenum"    
    page_size_query_param = "size"   
    max_page_size = 100              