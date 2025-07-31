"""
Django views for monitoring endpoints.
"""
from django.http import HttpResponse, JsonResponse
from django.views import View
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .health.checks import get_system_health

class MetricsView(View):
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus format for scraping.
    """
    
    def get(self, request):
        """Return Prometheus metrics."""
        metrics_data = generate_latest()
        return HttpResponse(
            metrics_data,
            content_type=CONTENT_TYPE_LATEST
        )

class HealthView(View):
    """
    Health check endpoint.
    Returns system health status in JSON format.
    """
    
    def get(self, request):
        """Return system health status."""
        health_status = get_system_health()
        
        # Set appropriate HTTP status code
        if health_status['status'] == 'healthy':
            status_code = 200
        elif health_status['status'] == 'degraded':
            status_code = 207  # Multi-Status
        else:
            status_code = 503  # Service Unavailable
        
        return JsonResponse(
            health_status,
            status=status_code,
            json_dumps_params={'indent': 2}
        )