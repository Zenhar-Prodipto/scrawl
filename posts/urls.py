from django.urls import path
from .views import PostCreateView, PostDetailView

urlpatterns = [
    path('me/', PostCreateView.as_view(), name='create-post'),
    path('me/<int:post_id>/', PostDetailView.as_view(), name='post-detail'),
]