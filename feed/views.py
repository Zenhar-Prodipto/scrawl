from django.shortcuts import render
# feed/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import DatabaseError
from .services import get_user_feed
from posts.serializers import PostListSerializer
from .paginators import FeedPaginator

class FeedView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = FeedPaginator

    def get(self, request, *args, **kwargs):
        try:
            posts_with_source = get_user_feed(request.user)
            posts = [item["post"] for item in posts_with_source]
            sources = {item["post"].id: item["source"] for item in posts_with_source}

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(posts, request)

            serializer = PostListSerializer(page, many=True, context={'request': request, 'user': request.user})

            # Add source info to each serialized post
            serialized_data = serializer.data
            for post in serialized_data:
                post_id = post["id"]
                post["source"] = sources.get(post_id, "unknown")

            return paginator.get_paginated_response({
                "status": "success",
                "message": "Feed retrieved successfully",
                "data": serialized_data
            })
        except DatabaseError as e:
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )