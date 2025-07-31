from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import FollowRequestCancelSerializer, FollowRequestSerializerIncoming, FollowRequestSerializerOutgoing, FollowRequestUpdateSerializer, FollowSerializer, UserFollowSerializer, SelfUserFollowSerializer
from .services import FollowService
from users.services import UserService  
from users.models import User  
from django.db import DatabaseError
from .paginators import FollowPaginator
from rest_framework import serializers
from scrawl.core.rate_limiting.utils import rate_limit_user
from scrawl.core.monitoring.metrics.collectors import record_follow_interaction

class FollowView(generics.GenericAPIView):
    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]
    
    @rate_limit_user('follow')
    def post(self, request, user_id, *args, **kwargs):
        current_user = request.user
        serializer = self.get_serializer(data={'followed': user_id})
        
        try:
            serializer.is_valid(raise_exception=True)
            target_user = UserService.get_user_by_id(user_id)
            if target_user.profile_type == 'private':
                follow_status = FollowService.check_follow_status(current_user, user_id)
                if follow_status:
                    record_follow_interaction('follow', 'Bad Request', 'free')
                    return Response(
                        {"status": "error", "message": "you are already following this user"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # check if current user has already sent a follow request
                follow_requests_exists = FollowService.does_follow_request_exist(current_user, user_id)
                if follow_requests_exists:
                    record_follow_interaction('follow', 'bad request', 'free')
                    return Response(
                        {"status": "error", "message": "You have already sent a follow request to this user"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                #create a follow request
                FollowService.create_follow_request(current_user, user_id)
                record_follow_interaction('follow_request', 'create', 'free')
                
                return Response(
                    {
                        "status": "success",
                        "message": "Follow request sent successfully",
                        "data": UserFollowSerializer(target_user).data
                    },
                    status=status.HTTP_201_CREATED
                )
            
            follow = FollowService.follow_user(current_user, user_id)
            record_follow_interaction('follow', 'create', 'free')
            target_user = User.objects.get(id=user_id, is_deleted=False)
            target_data = UserFollowSerializer(target_user).data
            return Response(
                {
                    "status": "success",
                    "message": "Successfully followed the user",
                    "data": target_data
                },
                status=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            record_follow_interaction('follow', 'validation_failed', 'free')
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except User.DoesNotExist:
            record_follow_interaction('follow', 'user_not_found', 'free')
            return Response(
                {"status": "error", "message": "Target user not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            record_follow_interaction('follow', 'business_logic_failed', 'free')
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError:
            record_follow_interaction('follow', 'database_error', 'free')
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            record_follow_interaction('follow', 'unexpected_error', 'free')
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @rate_limit_user('follow')   
    def delete(self, request, user_id, *args, **kwargs):
        current_user = request.user
        try:
            follow_status = FollowService.check_follow_status(current_user, user_id)
            if not follow_status:
                record_follow_interaction('follow', 'unfollow_user_not_found', 'free')
                return Response(
                    {"status": "error", "message": "You are not following this user"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Get target user before unfollowing for response
            target_user = UserService.get_user_by_id(user_id)
            FollowService.unfollow_user(current_user, user_id)
            record_follow_interaction('follow', 'delete', 'free')
            target_data = UserFollowSerializer(target_user).data 
            return Response(
                {
                    "status": "success",
                    "message": "Successfully unfollowed the user",
                    "data": target_data
                },
                status=status.HTTP_200_OK 
            )
        except User.DoesNotExist:
            record_follow_interaction('follow', 'unfollow_user_not_found', 'free')
            return Response(
                {"status": "error", "message": "Target user not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            record_follow_interaction('follow', 'unfollow_failed', 'free')
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError:
            record_follow_interaction('follow', 'dunfollow_database_failed', 'free')
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class FollowersView(generics.GenericAPIView):
    serializer_class = UserFollowSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FollowPaginator
    
    @rate_limit_user('followers_view')
    def get(self, request, user_id, *args, **kwargs):
        try:
            # Check if the target user exists and get their profile type
            target_user = UserService.get_user_by_id(user_id)
            # Privacy check: If private and not following, deny access
            if target_user.profile_type == 'private':
                is_following = FollowService.check_follow_status(request.user, user_id)
                
                if not is_following and request.user != target_user:
                    return Response(
                        {"status": "error", "message": "Cannot view followers of private profile"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            followers = FollowService.get_followers(user_id)
            followers_count = FollowService.get_follower_count(user_id)
            paginator = self.pagination_class() 
            page = paginator.paginate_queryset(followers, request, self)
            serializer = self.get_serializer(page, many=True)
            return paginator.get_paginated_response({
                "status": "success",
                "message": "Followers retrieved successfully",
                "data": serializer.data,
                "followers_count": followers_count
            })
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Target user not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class FollowingView(generics.GenericAPIView):
    serializer_class = UserFollowSerializer 
    permission_classes = [IsAuthenticated]
    pagination_class = FollowPaginator
    @rate_limit_user('following_view')
    def get(self, request, user_id, *args, **kwargs):
        try:
            # Check if the target user exists and get their profile type
            target_user = UserService.get_user_by_id(user_id)
            
            # Privacy check: If private and not following, deny access
            if target_user.profile_type == 'private':
                is_following = FollowService.check_follow_status(request.user, user_id)
                if not is_following and request.user != target_user:
                    return Response(
                        {"status": "error", "message": "Cannot view followers of private profile"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            following = FollowService.get_following(user_id)
            following_count = FollowService.get_following_count(user_id)
            paginator = self.pagination_class() 
            page = paginator.paginate_queryset(following, request, self)
            serializer = self.get_serializer(page, many=True)
            return paginator.get_paginated_response({
                "status": "success",
                "message": "Following retrieved successfully",
                "data": serializer.data,
                "following_count": following_count
            })
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Target user not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class SelfFollowersView(generics.ListAPIView):
    serializer_class = SelfUserFollowSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FollowPaginator
    
    def get_queryset(self):
        current_user = self.request.user
        return FollowService.get_followers(current_user.id)
    
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            followers_count = FollowService.get_follower_count(self.request.user.id)
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "status": "success",
                "message": "Followers retrieved successfully",
                "data": serializer.data,
                "followers_count": followers_count
            })
        
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Current user not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class SelfFollowingView(generics.ListAPIView):
    serializer_class = SelfUserFollowSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FollowPaginator
    
    def get_queryset(self):
        current_user = self.request.user
        return FollowService.get_following(current_user.id)
    
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            following_count = FollowService.get_following_count(self.request.user.id)
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "status": "success",
                "message": "Following retrieved successfully",
                "data": serializer.data,
                "following_count": following_count
            })
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Current user not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class FollowStatusView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    @rate_limit_user('follow_status')
    def get(self, request, user_id, *args, **kwargs):
        current_user = request.user
        try:
            is_following = FollowService.check_follow_status(current_user, user_id)
            return Response(
                {
                    "status": "success",
                    "message": "Follow status retrieved successfully",
                    "data": {"is_following": is_following}
                },
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Target user not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class PendingFollowRequestsIncomingView(generics.ListAPIView):
    serializer_class = FollowRequestSerializerIncoming
    permission_classes = [IsAuthenticated]
    pagination_class = FollowPaginator
    
    def get_queryset(self):
        current_user = self.request.user
        return FollowService.follow_requests_incoming(current_user)
    @rate_limit_user('pending_follow_requests_incoming')
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "status": "success",
                "message": "Pending follow requests retrieved successfully",
                "data": serializer.data
            })
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Current user not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class PendingFollowRequestsOutgoingView(generics.ListAPIView):
    serializer_class = FollowRequestSerializerOutgoing
    permission_classes = [IsAuthenticated]
    pagination_class = FollowPaginator
    
    def get_queryset(self):
        current_user = self.request.user
        return FollowService.follow_requests_outgoing(current_user)
    @rate_limit_user('pending_follow_requests_outgoing')
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "status": "success",
                "message": "Pending outgoing follow requests retrieved successfully",
                "data": serializer.data
            })
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Current user not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class FollowRequestUpdateView(generics.GenericAPIView):
    serializer_class = FollowRequestUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    @rate_limit_user('follow_request_update')
    def post(self, request, req_id, *args, **kwargs):
        try:
            # Validate request body
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            new_status = serializer.validated_data['status']
            current_user = request.user

            # Update the follow request
            FollowService.update_follow_request(current_user, req_id, new_status)

            # Return appropriate success message
            if new_status == 'accepted':
                record_follow_interaction('follow_request', 'accepted', 'free')
                message = "Follow request accepted successfully"
            else:  # denied
                message = "Follow request denied successfully"
                record_follow_interaction('follow_request', 'denied', 'free')

            return Response(
                {
                    "status": "success",
                    "message": message
                },
                status=status.HTTP_200_OK
            )

        except ValueError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class FollowRequestCancelView(generics.GenericAPIView):
    serializer_class = FollowRequestCancelSerializer
    permission_classes = [IsAuthenticated]
    @rate_limit_user('follow_request_cancel')
    def post(self, request, req_id, *args, **kwargs):
        try:
            # Validate request body (status will be 'cancelled')
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            current_user = request.user
            # Update the follow request
            FollowService.cancel_follow_request(current_user, req_id)
            record_follow_interaction('follow_request', 'cancelled', 'free')

            return Response(
                {
                    "status": "success",
                    "message": "Follow request cancelled successfully"
                },
                status=status.HTTP_200_OK
            )

        except ValueError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )