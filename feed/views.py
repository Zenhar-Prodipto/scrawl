from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import DatabaseError
from .services import FeedService
from posts.serializers import PostListSerializer
from scrawl.core.rate_limiting.utils import rate_limit_user
import logging

logger = logging.getLogger(__name__)

class FeedView(APIView):
    permission_classes = [IsAuthenticated]
    @rate_limit_user('feed_request')
    def get(self, request, *args, **kwargs):
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
            force_refresh = request.query_params.get('refresh', 'false').lower() == 'true'

            if force_refresh:
                FeedService.invalidate_user_feed(request.user.id)
                logger.info(f"Force refresh for user {request.user.id}")

            feed_data = FeedService.get_user_feed(request.user, page)
            posts = [item["post"] for item in feed_data['posts']]
            sources = {item["post"].id: item["source"] for item in feed_data['posts']}

            serializer = PostListSerializer(posts, many=True, context={'request': request, 'user': request.user})
            serialized_data = serializer.data

            for post_data in serialized_data:
                post_id = post_data["id"]
                post_data["source"] = sources.get(post_id, "unknown")

            response_data = {
                "status": "success",
                "message": "Feed retrieved successfully",
                "data": serialized_data,
                "pagination": {
                    "page": feed_data['page'],
                    "has_more": feed_data['has_more'],
                    "total_pages": feed_data['total_pages']
                },
                "meta": {
                    "cache_hit": feed_data.get('cache_hit', False),
                    "post_count": len(serialized_data)
                }
            }

            response = Response(response_data, status=status.HTTP_200_OK)
            if feed_data.get('cache_hit', False):
                response['X-Cache-Status'] = 'HIT'
            else:
                response['X-Cache-Status'] = 'MISS'
            if feed_data['has_more']:
                response['X-Has-More'] = 'true'
                response['X-Next-Page'] = str(page + 1)
            else:
                response['X-Has-More'] = 'false'

            logger.info(f"Feed request for user {request.user.id}: page={page}, posts={len(serialized_data)}, cache_hit={feed_data.get('cache_hit', False)}")
            return response

        except ValueError as e:
            logger.warning(f"Invalid params for user {request.user.id}: {e}")
            return Response({"status": "error", "message": "Invalid request parameters", "errors": {"detail": str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"Database error for user {request.user.id}: {e}")
            return Response({"status": "error", "message": "Database error", "errors": {"detail": "Unable to retrieve feed"}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Unexpected error for user {request.user.id}: {e}", exc_info=True)
            return Response({"status": "error", "message": "Unexpected error", "errors": {"detail": str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)