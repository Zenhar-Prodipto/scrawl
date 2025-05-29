from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class PostPaginator(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
            # Flatten the response by merging pagination metadata with the data dict
            return Response({
                "status": "success",
                "message": data.get("message", "Retrieved successfully"),  # Default message
                "data": data["data"],  # Extract the serialized data
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                **{key: value for key, value in data.items() if key not in ["status", "message", "data"]}  # Merge extra fields (e.g., followers_count)
            })