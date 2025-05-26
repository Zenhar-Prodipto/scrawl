from django.urls import path
from .views import PostCreateView

urlpatterns = [
    path('me/', PostCreateView.as_view(), name='create-post'),
]