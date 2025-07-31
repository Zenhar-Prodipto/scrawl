from django.shortcuts import render
# Create your views here.
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from .services import PostService
from .models import Post, Like, User, Comment
from .serializers import LikeCreateSerializer
from .serializers import PostCreateSerializer, PostDetailSerializer, PostListSerializer, PostUpdateSerializer, LikeCreateSerializer, CommentCreateSerializer, CommentUpdateSerializer
from .paginators import PostPaginator
from scrawl.core.rate_limiting.utils import rate_limit_user
from scrawl.core.monitoring.metrics.collectors import record_post_interaction

class PostCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @rate_limit_user('post_create')
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
            record_post_interaction('post', 'create_validation_failed', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValueError as e:
            record_post_interaction('post', 'create_business_error', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "errors": {}
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            record_post_interaction('post', 'database_error', 'unknown', 'free')

            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('post', 'unexpected_error', 'unknown', 'free')

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

    @rate_limit_user('post_view')
    def get(self, request, post_id, *args, **kwargs):
        try:
            post = PostService.get_self_post_by_id(post_id, request.user)
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
    @rate_limit_user('post_update') 
    def patch(self, request, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_self_post_by_id(post_id, request.user)
            
            # Serialize and validate the update data
            serializer = PostUpdateSerializer(post, data=request.data, context={'request': request}, partial=True)
            if serializer.is_valid():
                updated_post = serializer.save(user=request.user)
                record_post_interaction('post', 'update', updated_post.privacy, 'free')
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
            record_post_interaction('post', 'update_validation_failed', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except ObjectDoesNotExist as e:
            record_post_interaction('post', 'update_business_error', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('post', 'update_database_error', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('post', 'update_unexpected_error', 'unknown', 'free') 
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @rate_limit_user('post_delete')  
    def delete(self, request, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_self_post_by_id(post_id, request.user)
            post_privacy = post.privacy
            
            # Delete the post (cascades to related objects)
            post.delete()
            record_post_interaction('post', 'delete', post_privacy, 'free')
            
            return Response(
                {
                    "status": "success",
                    "message": "Post deleted successfully",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )
        except ObjectDoesNotExist as e:
            record_post_interaction('post', 'delete_business_error', 'unknown', 'free') 
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('post', 'delete_database_error', 'unknown', 'free') 
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('post', 'delete_unexpected_error', 'unknown', 'free') 
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

    @rate_limit_user('post_list_view')
    def get(self, request, *args, **kwargs):
        try:
            # Fetch posts
            posts = PostService.get_user_posts(request.user)
            
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
    @rate_limit_user('like_post')
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
            post = PostService.get_post_by_id(post_id)
            
            # Check eligibility to like the post
            if not PostService.check_like_eligibility(request.user, post):
                record_post_interaction('like', 'Not_eligible', 'unknown', 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "You are not eligible to like this post.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Create the like
            like = PostService.create_like(request.user, post)
            record_post_interaction('like', 'create', post.privacy, 'free')

            return Response(
                {
                    "status": "success",
                    "message": "Post liked successfully",
                    "data": {"like_id": like.id}
                },
                status=status.HTTP_201_CREATED
            )

        except Post.DoesNotExist:
            record_post_interaction('like', 'post_not_found', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except User.DoesNotExist as e:
            record_post_interaction('like', 'user_not_found', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "User not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('like', 'Database_error', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('like', 'Database_error', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @rate_limit_user('like_post')  
    def delete(self, request, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_post_by_id(post_id)
            
            # Check if the user has liked the post
            like_exists = PostService.check_if_like_exists(request.user, post)
            if not like_exists:
                return Response(
                    {
                        "status": "error",
                        "message": "You have not liked this post.",
                        "errors": {}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Delete the like
            PostService.delete_like(request.user, post)
            record_post_interaction('like', 'delete', post.privacy, 'free')


            return Response(
                {
                    "status": "success",
                    "message": "Post unliked successfully",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )

        except Post.DoesNotExist:
            record_post_interaction('like', 'post_not_found', 'unknown', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('like', 'Database_error', 'unknown', 'free')
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
        
class CommentPostView(APIView):
    permission_classes = [IsAuthenticated]
    @rate_limit_user('comment_post')
    def post(self, request, post_id, *args, **kwargs):
        try:
            # Validate request data
            serializer = CommentCreateSerializer(data=request.data)
            if not serializer.is_valid():
                record_post_interaction('comment', 'create_validation_fail', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "Validation failed",
                        "errors": serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch the post
            post = PostService.get_post_by_id(post_id)
            
            # Check eligibility to comment on the post
            if not PostService.check_comment_eligibility(request.user, post):
                record_post_interaction('comment', 'create_not_eligible', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "You are not eligible to comment on this post.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Create the comment
            comment = PostService.create_comment(request.user, post, serializer.validated_data['text'])
            record_post_interaction('comment', 'create', post.privacy, 'free')

            return Response(
                {
                    "status": "success",
                    "message": "Comment created successfully",
                    "data": {"comment_id": comment.id}
                },
                status=status.HTTP_201_CREATED
            )

        except Post.DoesNotExist:
            record_post_interaction('comment', 'post_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except User.DoesNotExist as e:
            record_post_interaction('comment', 'user_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "User not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('comment', 'database_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('comment', 'unexpected_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @rate_limit_user('comment_post')   
    def patch(self, request, post_id, comment_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_post_by_id(post_id)
            
            # Fetch the comment
            comment = PostService.get_comment_by_id(comment_id, post)
            
            print("Comment:{comment}", flush=True)
            
            # Check if the requesting user is the comment creator
            if request.user != comment.user:
                record_post_interaction('comment', 'update_not_owner', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "You are not authorized to update this comment.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check eligibility to interact with the post
            if not PostService.check_comment_eligibility(request.user, post):
                record_post_interaction('comment', 'update_not_eligible', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "You are not eligible to update this comment.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Validate update data
            serializer = CommentUpdateSerializer(data=request.data, partial=True)
            if not serializer.is_valid():
                record_post_interaction('comment', 'update_validation_failed', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "Validation failed",
                        "errors": serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update the comment
            updated_comment = PostService.update_comment(comment, serializer.validated_data.get('text', comment.text))
            record_post_interaction('comment', 'update', post.privacy, 'free')


            return Response(
                {
                    "status": "success",
                    "message": "Comment updated successfully",
                    "data": {"comment_id": updated_comment.id, "text": updated_comment.text}
                },
                status=status.HTTP_200_OK
            )

        except Comment.DoesNotExist:
            record_post_interaction('comment', 'comment_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Comment not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Post.DoesNotExist:
            record_post_interaction('comment', 'post_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('comment', 'database_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('comment', 'unexpected_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @rate_limit_user('comment_post')      
    def delete(self, request, post_id, comment_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_post_by_id(post_id)
            
            # Fetch the comment
            comment = PostService.get_comment_by_id(comment_id, post)
            
            # Check if the requesting user is the post owner (can delete any comment)
            if request.user == post.user:
                PostService.delete_comment(comment)
                record_post_interaction('comment', 'delete', post.privacy, 'free')
                return Response(
                    {
                        "status": "success",
                        "message": "Comment deleted successfully",
                        "data": {}
                    },
                    status=status.HTTP_200_OK
                )
                
            #print the comment I get from the database to see data for debugging
            print("Comment fetched for deletion:", comment, flush=True)
            
            # If not the post owner, check if the user is the comment creator
            if request.user == comment.user:
                # Check eligibility for non-owners
                if not PostService.check_comment_eligibility(request.user, post):
                    record_post_interaction('comment', 'delete_not_eligible', post.privacy, 'free')
                    return Response(
                        {
                            "status": "error",
                            "message": "You are not eligible to delete this comment.",
                            "errors": {}
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
                PostService.delete_comment(comment)
                record_post_interaction('comment', 'delete', post.privacy, 'free')
                return Response(
                    {
                        "status": "success",
                        "message": "Comment deleted successfully",
                        "data": {}
                    },
                    status=status.HTTP_200_OK
                )

            # If neither post owner nor comment creator, deny access
            record_post_interaction('comment', 'delete_not_authorized', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "You are not authorized to delete this comment.",
                    "errors": {}
                },
                status=status.HTTP_403_FORBIDDEN
            )

        except Comment.DoesNotExist:
            record_post_interaction('comment', 'comment_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Comment not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Post.DoesNotExist:
            record_post_interaction('comment', 'post_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('comment', 'database_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('comment', 'unexpected_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class SavePostView(APIView):
    permission_classes = [IsAuthenticated]

    @rate_limit_user('save_post')
    def post(self, request, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_post_by_id(post_id)
            
            # Check eligibility (same as like/comment, allows self-saves)
            if not PostService.check_save_eligibility(request.user, post):
                record_post_interaction('save', 'create_not_eligible', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "You are not eligible to save this post.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if already saved
            if PostService.get_save_by_user_and_post(request.user, post):
                record_post_interaction('save', 'create_already_saved', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "Post is already saved.",
                        "errors": {}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create save
            PostService.create_save(request.user, post)
            record_post_interaction('save', 'create', post.privacy, 'free')
            
            return Response(
                {
                    "status": "success",
                    "message": "Post saved successfully",
                    "data": {"post_id": post.id}
                },
                status=status.HTTP_201_CREATED
            )

        except Post.DoesNotExist:
            record_post_interaction('save', 'post_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('save', 'database_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('save', 'unexpected_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @rate_limit_user('save_post')
    def delete(self, request, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_post_by_id(post_id)
            
            # Check if saved
            if not PostService.get_save_by_user_and_post(request.user, post):
                record_post_interaction('save', 'delete_post_not_saved', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "Post is not saved.",
                        "errors": {}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if not PostService.check_save_eligibility(request.user, post):
                record_post_interaction('save', 'delete_not_eligible', post.privacy, 'free')
                return Response(
                    {
                        "status": "error",
                        "message": "You are not eligible to save this post.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Delete save
            PostService.delete_save(request.user, post)
            record_post_interaction('save', 'delete', post.privacy, 'free')

            
            return Response(
                {
                    "status": "success",
                    "message": "Post unsaved successfully",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )

        except Post.DoesNotExist:
            record_post_interaction('save', 'post_not_found', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Post not found.",
                    "errors": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            record_post_interaction('save', 'database_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Database error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_post_interaction('save', 'unexpected_error', post.privacy, 'free')
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred",
                    "errors": {"detail": str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class SavedPostListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = PostPaginator

    @rate_limit_user('saved_posts_view')
    def get(self, request, *args, **kwargs):
        try:
            # Fetch the user's saved posts
            posts = PostService.get_user_saved_posts(request.user)
            
            # Paginate the queryset
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(posts, request)
            
            # Serialize the paginated data
            serializer = PostListSerializer(page, many=True, context={'request': request, 'user': request.user})
            
            # Return paginated response
            return paginator.get_paginated_response({
                "status": "success",
                "message": "Saved posts retrieved successfully",
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
            
class UserPostListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = PostPaginator
    @rate_limit_user('user_posts_view')
    def get(self, request, user_id, *args, **kwargs):
        try:
            # Fetch posts for the specified user
            posts = PostService.get_user_posts_by_id(user_id)
            
            # Check eligibility for each post
            eligible_posts = []
            for post in posts:
                if PostService.post_view_eligibility(request.user, post):
                    eligible_posts.append(post)
            
            # Paginate the eligible posts
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(eligible_posts, request)
            
            # Serialize the paginated data
            serializer = PostListSerializer(page, many=True, context={'request': request, 'user': request.user})
            
            # Return paginated response
            return paginator.get_paginated_response({
                "status": "success",
                "message": "User posts retrieved successfully",
                "data": serializer.data
            })
            
        except User.DoesNotExist:
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
            
class UserPostDetailView(APIView):
    permission_classes = [IsAuthenticated]
    @rate_limit_user('user_post_view_details')
    def get(self, request, user_id, post_id, *args, **kwargs):
        try:
            # Fetch the post
            post = PostService.get_post_by_id(post_id)
            
            # Verify the post belongs to the specified user
            if post.user.id != user_id:
                return Response(
                    {
                        "status": "error",
                        "message": "Post does not belong to the specified user.",
                        "errors": {}
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check eligibility to view the post
            if not PostService.post_view_eligibility(request.user, post):
                return Response(
                    {
                        "status": "error",
                        "message": "You are not eligible to view this post.",
                        "errors": {}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Serialize the post
            serializer = PostDetailSerializer(post, context={'request': request})
            
            return Response(
                {
                    "status": "success",
                    "message": "Post retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
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
        except User.DoesNotExist:
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
