from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import FollowSerializer, UserFollowSerializer
from .services import follow_user, unfollow_user,get_followers,get_following,check_follow_status
from users.models import User  # Added
from django.db import DatabaseError
from rest_framework import serializers

class FollowView(generics.GenericAPIView):
    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request, user_id, *args, **kwargs):
        current_user = request.user
        serializer = self.get_serializer(data={'followed': user_id})
        
        try:
            serializer.is_valid(raise_exception=True)
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
            # Get target user before unfollowing for response
            target_user = User.objects.get(id=user_id, is_deleted=False)
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
    
    def get(self, request, user_id, *args, **kwargs):
        try:
            followers = get_followers(user_id)
            serializer = self.get_serializer(followers, many=True)
            return Response(
                {
                    "status": "success",
                    "message": "Followers retrieved successfully",
                    "data": serializer.data
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
            
class FollowingView(generics.GenericAPIView):
    serializer_class = UserFollowSerializer 
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id, *args, **kwargs):
        try:
            following = get_following(user_id)
            serializer = self.get_serializer(following, many=True)
            return Response(
                {
                    "status": "success",
                    "message": "Following retrieved successfully",
                    "data": serializer.data
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