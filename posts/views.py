from django.shortcuts import render
# Create your views here.
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from .services import get_self_post_by_id, get_post_by_id, get_user_posts, check_like_eligibility, create_like
from .models import Post, Like, User
from .serializers import LikeCreateSerializer
from .serializers import PostCreateSerializer, PostDetailSerializer, PostListSerializer, PostUpdateSerializer
from .paginators import PostPaginator

class PostCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            serializer = PostCreateSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                post = serializer.save(user=request.user)
                return Response(
                    {
                        "status": "success",
                        "message": "Post created successfully",
                        "data": {"id": post.id}
                    },
                    status=status.HTTP_201_CREATED
                )
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValueError as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "errors": {}
                },
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
            
class PostDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, post_id, *args, **kwargs):
        try:
            post = get_self_post_by_id(post_id, request.user)
            serializer = PostDetailSerializer(post, context={'request': request})
            return Response(
                {
                    "status": "success",
                    "message": "Post retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        except ObjectDoesNotExist as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
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
            
    def patch(self, request, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = get_self_post_by_id(post_id, request.user)
            
            # Serialize and validate the update data
            serializer = PostUpdateSerializer(post, data=request.data, context={'request': request}, partial=True)
            if serializer.is_valid():
                updated_post = serializer.save(user=request.user)
                # Serialize the updated post for response
                response_serializer = PostDetailSerializer(updated_post, context={'request': request})
                return Response(
                    {
                        "status": "success",
                        "message": "Post updated successfully",
                        "data": response_serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except ObjectDoesNotExist as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
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
            
    def delete(self, request, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = get_self_post_by_id(post_id, request.user)
            
            # Delete the post (cascades to related objects)
            post.delete()
            
            return Response(
                {
                    "status": "success",
                    "message": "Post deleted successfully",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )
        except ObjectDoesNotExist as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
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
            
class PostListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = PostPaginator

    def get(self, request, *args, **kwargs):
        try:
            # Fetch posts
            posts = get_user_posts(request.user)
            
            # Paginate the queryset
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(posts, request)
            
            # Serialize the paginated data
            serializer = PostListSerializer(page, many=True, context={'request': request})
            
            # Return paginated response
            return paginator.get_paginated_response({
                "status": "success",
                "message": "Posts retrieved successfully",
                "data": serializer.data
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
            
class LikePostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id, *args, **kwargs):
        try:
            # Validate request data
            serializer = LikeCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status": "error",
                        "message": "Validation failed",
                        "errors": serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch the post
            post = get_post_by_id(post_id)
            
            # Check eligibility to like the post
            if not check_like_eligibility(request.user, post):
                return Response(
                    {
                        "status": "error",
                        "message": "You are not eligible to like this post.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Create the like
            like = create_like(request.user, post)

            return Response(
                {
                    "status": "success",
                    "message": "Post liked successfully",
                    "data": {"like_id": like.id}
                },
                status=status.HTTP_201_CREATED
            )

        except Post.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except User.DoesNotExist as e:
            return Response(
                {
                    "status": "error",
                    "message": "User not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
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