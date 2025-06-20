from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import DatabaseError
from .services import get_user_feed
from posts.serializers import PostListSerializer

class FeedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            page = int(request.query_params.get('page', 1))
            posts_with_source = get_user_feed(request.user, page)

            # Enforce source order: followed, interaction, interest, followed_remaining
            source_priority = {
                "followed": 0,
                "interaction": 1,
                "interest": 2,
                "followed_remaining": 3
            }
            posts_with_source.sort(
                key=lambda x: (source_priority.get(x["source"], 99), -x["post"].created_at.timestamp())
            )

            posts = [item["post"] for item in posts_with_source]
            sources = {item["post"].id: item["source"] for item in posts_with_source}

            serializer = PostListSerializer(posts, many=True, context={'request': request, 'user': request.user})

            # Add source info to each serialized post
            serialized_data = serializer.data
            for post in serialized_data:
                post_id = post["id"]
                post["source"] = sources.get(post_id, "unknown")

            # Build manual pagination metadata
            has_next = len(posts) == 10  # If you always want 10 per batch
            next_page = page + 1 if has_next else None
            previous_page = page - 1 if page > 1 else None

            return Response({
                "status": "success",
                "message": "Feed retrieved successfully",
                "data": serialized_data,
                "count": len(serialized_data),
                "next": f"?page={next_page}" if has_next else None,
                "previous": f"?page={previous_page}" if previous_page else None,
            })
        except ValueError:
            return Response(
                {"status": "error", "message": "Invalid page parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
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