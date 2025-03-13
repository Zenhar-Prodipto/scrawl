from django.urls import path
from follows.views import FollowView, FollowersView, FollowingView,FollowStatusView
urlpatterns = [
    path('<int:user_id>/follow/', FollowView.as_view(), name='follow-unfollow'),
    path('<int:user_id>/followers/', FollowersView.as_view(), name='followers'),
    path('<int:user_id>/following/', FollowingView.as_view(), name='following'),
    path('<int:user_id>/status/', FollowStatusView.as_view(), name='follow-status')
    
]