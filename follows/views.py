from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import FollowRequestCancelSerializer, FollowRequestSerializerIncoming, FollowRequestSerializerOutgoing, FollowRequestUpdateSerializer, FollowSerializer, UserFollowSerializer, SelfUserFollowSerializer
from .services import cancel_follow_request, create_follow_request, does_follow_request_exist, follow_requests_incoming, follow_requests_outgoing, follow_user, get_follower_count, get_following_count, unfollow_user,get_followers,get_following,check_follow_status, update_follow_request
from users.services import get_user_by_id  
from users.models import User  
from django.db import DatabaseError
from .paginators import FollowPaginator
from rest_framework import serializers

class FollowView(generics.GenericAPIView):
    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request, user_id, *args, **kwargs):
        current_user = request.user
        serializer = self.get_serializer(data={'followed': user_id})
        
        try:
            serializer.is_valid(raise_exception=True)
            target_user = get_user_by_id(user_id)
            if target_user.profile_type == 'private':
                follow_status = check_follow_status(current_user, user_id)
                if follow_status:
                    return Response(
                        {"status": "error", "message": "you are already following this user"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # check if current user has already sent a follow request
                follow_requests_exists = does_follow_request_exist(current_user, user_id)
                if follow_requests_exists:
                    return Response(
                        {"status": "error", "message": "You have already sent a follow request to this user"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                #create a follow request
                create_follow_request(current_user, user_id)
                
                return Response(
                    {
                        "status": "success",
                        "message": "Follow request sent successfully",
                        "data": UserFollowSerializer(target_user).data
                    },
                    status=status.HTTP_201_CREATED
                )
            
            follow = follow_user(current_user, user_id)
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
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "Target user not found"},
                status=status.HTTP_404_NOT_FOUND
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
            
    def delete(self, request, user_id, *args, **kwargs):
        current_user = request.user
        try:
            follow_status = check_follow_status(current_user, user_id)
            if not follow_status:
                return Response(
                    {"status": "error", "message": "You are not following this user"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Get target user before unfollowing for response
            target_user = get_user_by_id(user_id)
            unfollow_user(current_user, user_id)
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
            return Response(
                {"status": "error", "message": "Target user not found"},
                status=status.HTTP_404_NOT_FOUND
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
            
class FollowersView(generics.GenericAPIView):
    serializer_class = UserFollowSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FollowPaginator
    
    def get(self, request, user_id, *args, **kwargs):
        try:
            # Check if the target user exists and get their profile type
            target_user = get_user_by_id(user_id)
            # Privacy check: If private and not following, deny access
            if target_user.profile_type == 'private':
                is_following = check_follow_status(request.user, user_id)
                
                if not is_following and request.user != target_user:
                    return Response(
                        {"status": "error", "message": "Cannot view followers of private profile"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            followers = get_followers(user_id)
            followers_count = get_follower_count(user_id)
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
    
    def get(self, request, user_id, *args, **kwargs):
        try:
            # Check if the target user exists and get their profile type
            target_user = get_user_by_id(user_id)
            
            # Privacy check: If private and not following, deny access
            if target_user.profile_type == 'private':
                is_following = check_follow_status(request.user, user_id)
                if not is_following and request.user != target_user:
                    return Response(
                        {"status": "error", "message": "Cannot view followers of private profile"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            following = get_following(user_id)
            following_count = get_following_count(user_id)
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
        return get_followers(current_user.id)
    
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            followers_count = get_follower_count(self.request.user.id)
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
        return get_following(current_user.id)
        
    
    def list(self,request,*args,**kwargs):
        try:
            queryset = self.get_queryset()
            following_count = get_following_count(self.request.user.id)
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
    
    def get(self, request, user_id, *args, **kwargs):
        current_user = request.user
        try:
            is_following = check_follow_status(current_user, user_id)
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
        return follow_requests_incoming(current_user)
        
    
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
        return follow_requests_outgoing(current_user)
    
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
    
    def post(self, request, req_id, *args, **kwargs):
        try:
            # Validate request body
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            new_status = serializer.validated_data['status']
            current_user = request.user

            # Update the follow request
            update_follow_request(current_user, req_id, new_status)

            # Return appropriate success message
            if new_status == 'accepted':
                message = "Follow request accepted successfully"
            else:  # denied
                message = "Follow request denied successfully"

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
    
    def post(self, request, req_id, *args, **kwargs):
        try:
            # Validate request body (status will be 'cancelled')
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            current_user = request.user
            # Update the follow request
            cancel_follow_request(current_user, req_id)

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