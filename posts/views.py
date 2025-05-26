from django.shortcuts import render
# Create your views here.
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from .services import get_post_by_id
from .serializers import PostCreateSerializer, PostDetailSerializer

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
            post = get_post_by_id(post_id, request.user)
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