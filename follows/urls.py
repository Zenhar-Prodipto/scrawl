from django.urls import path
from follows.views import FollowView 
urlpatterns = [
    path('<int:user_id>/follow/', FollowView.as_view(), name='follow-unfollow'),
]