"""
URL configuration for monitoring endpoints.
"""
from django.urls import path
from .views import MetricsView, HealthView

urlpatterns = [
    path('metrics', MetricsView.as_view(), name='prometheus-metrics'),
    path('health', HealthView.as_view(), name='system-health'),
]