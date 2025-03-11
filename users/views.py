from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import DatabaseError
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated
from .serializers import RegisterSerializer, LoginSerializer,LogoutSerializer,InterestSerializer
from rest_framework import serializers
from .serializers import UserSerializer
from .services import get_interests,get_user_by_email,match_password

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

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
            user = serializer.save()  # Calls create_user in service
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

        user_data = UserSerializer(user).data # Use UserSerializer to include interests
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
                    "interests": user_data['interests'],  # Now included
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh)
                }
            },
            status=status.HTTP_201_CREATED
        )
        
        

class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

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
            user = get_user_by_email(serializer.validated_data['email']) 
            is_password_correct = match_password(user,serializer.validated_data['password'])
            
            
            if not user or not is_password_correct:
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
        
class InterestsView(generics.ListAPIView):
    serializer_class = InterestSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return get_interests()
    
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
            
  