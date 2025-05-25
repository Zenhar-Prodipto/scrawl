from django.urls import path
from follows.views import FollowView, FollowersView, FollowingView,FollowStatusView, PendingFollowRequestsIncomingView, PendingFollowRequestsOutgoingView, SelfFollowingView, SelfFollowersView
urlpatterns = [
    path('<int:user_id>/follow/', FollowView.as_view(), name='follow-unfollow'),
    path('<int:user_id>/followers/', FollowersView.as_view(), name='followers'),
    path('<int:user_id>/following/', FollowingView.as_view(), name='following'),
    path('me/following/', SelfFollowingView.as_view(), name='my-following'),
    path('me/followers/', SelfFollowersView.as_view(), name='my-followers'),
    path('<int:user_id>/status/', FollowStatusView.as_view(), name='follow-status'),
    path('me/requests/incoming/', PendingFollowRequestsIncomingView.as_view(), name='my-pending-requests'),
    path('me/requests/outgoing/', PendingFollowRequestsOutgoingView.as_view(), name='my-pending-requests-outgoing'),
    
]