"""
Safe API metrics middleware that avoids all import conflicts.
Uses basic Python logging and can be converted to Prometheus later.
"""
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve, Resolver404

# Create a dedicated logger for API metrics
api_metrics_logger = logging.getLogger('scrawl.api_metrics')

class APIMetricsMiddleware(MiddlewareMixin):
    """
    Safe middleware that logs API metrics without any imports
    from the monitoring system that could cause circular import issues.
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.get_response = get_response
        
    def process_request(self, request):
        """Start timing the request."""
        request._start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log API metrics AND feed Prometheus safely."""
        # Only track API endpoints
        if not self._is_api_request(request):
            return response
            
        try:
            # Calculate duration
            start_time = getattr(request, '_start_time', time.time())
            duration = time.time() - start_time
            
            # Get request info
            method = request.method.upper()
            path = request.path_info
            status_code = response.status_code
            user_info = self._get_user_info(request)
            endpoint = self._get_endpoint_name(request)
            
            # Extract user tier for Prometheus
            user_tier = self._extract_user_tier(request)
            
            # LOG the metrics (keeps working as before)
            api_metrics_logger.info(
                f"API_METRIC method={method} endpoint={endpoint} "
                f"status={status_code} duration={duration:.3f}s "
                f"user={user_info} path={path}"
            )
            
            # PROMETHEUS metrics (safe runtime import)
            self._record_prometheus_metrics(method, endpoint, status_code, user_tier, duration)
            
            # Add debug headers
            if hasattr(response, 'headers'):
                response.headers['X-Response-Time'] = f"{duration:.3f}s"
                response.headers['X-Endpoint'] = endpoint
                response.headers['X-Metrics'] = 'logged+prometheus'
            
        except Exception as e:
            api_metrics_logger.error(f"Metrics logging failed: {e}")
            
        return response

    def _record_prometheus_metrics(self, method, endpoint, status_code, user_tier, duration):
        """Safely record to Prometheus without circular imports."""
        try:
            # Runtime import to avoid circular imports
            import importlib
            collectors_module = importlib.import_module('scrawl.core.monitoring.metrics.collectors')
            
            # Get the functions we need
            record_api_request = getattr(collectors_module, 'record_api_request')
            api_request_duration = getattr(collectors_module, 'api_request_duration')
            
            # Record the metrics
            record_api_request(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                user_tier=user_tier
            )
            
            api_request_duration.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
        except Exception as e:
            # If Prometheus fails, don't break the request
            api_metrics_logger.debug(f"Prometheus recording failed: {e}")

    def _extract_user_tier(self, request):
        """Extract user tier for Prometheus (without the username)."""
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
                return 'admin' if user.is_superuser else 'free'
            else:
                return 'anonymous'
        except:
            # If anything fails, return 'unknown'
            return 'unknown'
    
    def process_exception(self, request, exception):
        """Log metrics for exceptions."""
        if not self._is_api_request(request):
            return None
            
        try:
            start_time = getattr(request, '_start_time', time.time())
            duration = time.time() - start_time
            
            method = request.method.upper()
            path = request.path_info
            user_info = self._get_user_info(request)
            endpoint = self._get_endpoint_name(request)
            
            api_metrics_logger.error(
                f"API_METRIC method={method} endpoint={endpoint} "
                f"status=500 duration={duration:.3f}s "
                f"user={user_info} path={path} "
                f"exception={type(exception).__name__}"
            )
            
        except Exception as e:
            api_metrics_logger.error(f"Exception metrics logging failed: {e}")
            
        return None
    
    def _is_api_request(self, request):
        """Check if this is an API request."""
        path = request.path_info.lower()
        return any(pattern in path for pattern in ['/api/', '/metrics', '/health'])
    
    def _get_user_info(self, request):
        """Get user information safely."""
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
                tier = 'admin' if user.is_superuser else 'free'
                return f"{user.username}({tier})"
            else:
                return "anonymous"
        except:
            return "unknown"
    
    def _get_endpoint_name(self, request):
        """Get endpoint name safely."""
        try:
            resolved = resolve(request.path_info)
            
            if resolved.url_name:
                return resolved.url_name
                
            if hasattr(resolved.func, 'view_class'):
                view_class = resolved.func.view_class.__name__
                return self._convert_class_name(view_class)
                
            return self._parse_from_path(request.path_info)
            
        except:
            return self._parse_from_path(request.path_info)
    
    def _convert_class_name(self, class_name):
        """Convert view class name to endpoint name."""
        import re
        name = class_name.replace('View', '').replace('API', '')
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        return name or 'unknown'
    
    def _parse_from_path(self, path):
        """Parse endpoint from path."""
        clean_path = path.strip('/').replace('api/v1/', '')
        parts = [p for p in clean_path.split('/') if p and not p.isdigit()]
        
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1]}"
        elif len(parts) == 1:
            return parts[0]
        else:
            return 'unknown'