from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import DatabaseError
from rest_framework.permissions import IsAuthenticated
from .serializers import RegisterSerializer, LoginSerializer, LogoutSerializer, InterestSerializer, UpdateUserSerializer
from rest_framework import serializers
from .serializers import UserSerializer
from .services import UserService
from scrawl.core.rate_limiting.utils import rate_limit_user, rate_limit_ip


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    
    @rate_limit_ip('register')
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        # Validation errors handled here
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # DB or token errors handled here
        try:
            user = serializer.save()  # Calls create_user in service via serializer
            refresh = RefreshToken.for_user(user)  # Generate JWT
        except DatabaseError:
            return Response(
                {
                    "status": "error",
                    "message": "Failed to save user due to a database error."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:  # Catch token generation or other surprises
            return Response(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Success response
        user_data = UserSerializer(user).data
        return Response(
            {
                "status": "success",
                "message": "User registered and logged in successfully",
                "data": {
                    "id": user_data['id'],
                    "username": user_data['username'],
                    "email": user_data['email'],
                    "first_name": user_data['first_name'],
                    "last_name": user_data['last_name'],
                    "profile_picture": user_data['profile_picture'],
                    "interests": user_data['interests'],
                    "profile_type": user_data['profile_type'],
                    "bio": user_data['bio'],
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh)
                }
            },
            status=status.HTTP_201_CREATED
        )
        
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    
    @rate_limit_ip('login') 
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response(
                {"status": "error", "message": "Validation failed", "errors": e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user = UserService.get_user_by_email(serializer.validated_data['email'])
            is_password_correct = UserService.match_password(user, serializer.validated_data['password'])
            
            if not user or not is_password_correct or user.is_deleted:
                return Response(
                    {"status": "error", "message": "Invalid credentials"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            refresh = RefreshToken.for_user(user)
            user_data = UserSerializer(user).data
            return Response({
                "status": "success",
                "message": "User logged in successfully",
                "data": {
                    "id": user_data['id'],
                    "username": user_data['username'],
                    "email": user_data['email'],
                    "first_name": user_data['first_name'],
                    "last_name": user_data['last_name'],
                    "profile_picture": user_data['profile_picture'],
                    "interests": user_data['interests'],
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh)
                }
            }, status=status.HTTP_200_OK)
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"status": "error", "message": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]
    @rate_limit_user('logout')
    def post(self, request, *args, **kwargs):
        print(f"LogoutView: User={request.user}, Token={request.auth}", flush=True)
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response(
                {"status": "error", "message": "Validation failed", "errors": e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {"status": "success", "message": "Logged out successfully"},
            status=status.HTTP_200_OK
        )
        
class UserProfileView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        user = self.request.user
        if user.is_deleted:
            return None
        return user
    
    @rate_limit_user('profile_view')   
    def get(self, request, *args, **kwargs):
        try:
            user = self.get_object()
            if not user:
                return Response({"status": "error", "message": "Database error occurred"},
                                status=status.HTTP_404_NOT_FOUND)
            serializer = self.get_serializer(user)
            user_data = serializer.data
            return Response(
                {"status": "success", "message": "Here is your user profile", "data": user_data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"status": "error", "message": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Apply user-based rate limiting to profile updates        
    @rate_limit_user('profile_update')
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        if not user:
            return Response({"status": "error", "message": "user not found!"},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = UpdateUserSerializer(user, data=request.data, partial=True)

        try:
            serializer.is_valid(raise_exception=True)
            updated_user = serializer.save()
            updated_user_data = UserSerializer(updated_user).data
            
            return Response(
                {"status": "success", "message": "Here is your user profile", "data": updated_user_data},
                status=status.HTTP_200_OK
            )
        except serializers.ValidationError as e:
            return Response({
                "status": "error",
                "message": "Validation failed",
                "errors": e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({
                "status": "error",
                "message": str(e)  # e.g., "One or more interest IDs do not exist"
            }, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError:
            return Response({
                "status": "error",
                "message": "Database error occurred"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({
                "status": "error",
                "message": f"Unexpected error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        if not user:
            return Response({
                "status": "error",
                "message": "User Not Found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            updated_user = UserService.soft_delete_user(user)
            updated_user_data = UserSerializer(updated_user).data
            return Response(
                {"status": "success", "message": "Here is your user profile", "data": updated_user_data},
                status=status.HTTP_200_OK
            )
        except DatabaseError:
            return Response({"status": "error", "message": "Database error occurred"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"status": "error", "message": f"Unexpected error: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class InterestsView(generics.ListAPIView):
    serializer_class = InterestSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return UserService.get_interests()
    
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            interests_data = serializer.data
            return Response(
                {"status": "success", "data": interests_data},
                status=status.HTTP_200_OK
            )
        except DatabaseError:
            return Response(
                {"status": "error", "message": "Database error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"status": "error", "message": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )