from django.urls import path
from .views import PostCreateView, PostDetailView, PostListView,LikePostView

urlpatterns = [
    path('me/', PostCreateView.as_view(), name='create-post'),
    path('me/<int:post_id>/', PostDetailView.as_view(), name='post-detail'),
    path('me/list/', PostListView.as_view(), name='post-list'),
    path('<int:post_id>/like/', LikePostView.as_view(), name='like-post'),
]