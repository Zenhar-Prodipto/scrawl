from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import DatabaseError
from .serializers import RegisterSerializer
from rest_framework import serializers

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
        return Response(
            {
                "status": "success",
                "message": "User registered and logged in successfully",
                "data": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh)
                }
            },
            status=status.HTTP_201_CREATED
        )
        
        

            