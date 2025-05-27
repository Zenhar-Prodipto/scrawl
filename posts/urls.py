from django.urls import path
from .views import PostCreateView, PostDetailView, PostListView,LikePostView, CommentPostView

urlpatterns = [
    path('me/', PostCreateView.as_view(), name='create-post'),
    path('me/<int:post_id>/', PostDetailView.as_view(), name='post-detail'),
    path('me/list/', PostListView.as_view(), name='post-list'),
    path('<int:post_id>/like/', LikePostView.as_view(), name='like-post'),
    path('<int:post_id>/comment/', CommentPostView.as_view(), name='comment-post'),
    path('<int:post_id>/comment/<int:comment_id>/', CommentPostView.as_view(), name='comment-update-delete'),  # PATCH, DELETE
]