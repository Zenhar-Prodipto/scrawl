"""
Enhanced API metrics middleware with ELK integration.
Combines existing Prometheus metrics with structured ELK logging.
"""
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve, Resolver404

# API metrics logger
api_metrics_logger = logging.getLogger('scrawl.api_metrics')

# Add ELK structured logger
try:
    from .logging import get_elk_logger, create_log_context, EventTypes
    elk_logger = get_elk_logger()
    ELK_AVAILABLE = True
except ImportError:
    elk_logger = None
    ELK_AVAILABLE = False

class APIMetricsMiddleware(MiddlewareMixin):
    """
    Enhanced middleware that logs API metrics AND feeds ELK with structured logs.
    Maintains backward compatibility with existing monitoring.
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.get_response = get_response
        
    def process_request(self, request):
        """Start timing the request and add ELK correlation ID."""
        request._start_time = time.time()
        
        # Add ELK request ID for correlation
        if ELK_AVAILABLE:
            import uuid
            request._elk_request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        return None
    
    def process_response(self, request, response):
        """Log API metrics AND structured ELK logs."""
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
            user_tier = self._extract_user_tier(request)
            
            # Log to api_metrics 
            api_metrics_logger.info(
                f"API_METRIC method={method} endpoint={endpoint} "
                f"status={status_code} duration={duration:.3f}s "
                f"user={user_info} path={path}"
            )
            
            # Prometheus metrics 
            self._record_prometheus_metrics(method, endpoint, status_code, user_tier, duration)
            
            # ELK structured logging
            self._log_to_elk(request, response, method, endpoint, status_code, duration, user_tier)
            
            # Add debug headers
            if hasattr(response, 'headers'):
                response.headers['X-Response-Time'] = f"{duration:.3f}s"
                response.headers['X-Endpoint'] = endpoint
                response.headers['X-Metrics'] = 'logged+prometheus+elk'
                if ELK_AVAILABLE:
                    response.headers['X-Request-ID'] = getattr(request, '_elk_request_id', 'unknown')
            
        except Exception as e:
            api_metrics_logger.error(f"Metrics logging failed: {e}")
            
        return response

    def _log_to_elk(self, request, response, method, endpoint, status_code, duration, user_tier):
        """NEW: Send structured logs to ELK."""
        if not ELK_AVAILABLE:
            return
            
        try:
            # Get user object safely
            user = getattr(request, 'user', None) if hasattr(request, 'user') else None
            
            # Create log context
            context = create_log_context(request=request, user=user)
            
            # Enhanced context for API requests
            context.update({
                'event_type': EventTypes.API_REQUEST,
                'endpoint': endpoint,
                'status_code': status_code,
                'duration': round(duration, 3),
                'user_tier': user_tier,
                'response_size': len(response.content) if hasattr(response, 'content') else 0
            })
            
            # Determine log level based on status code
            if status_code >= 500:
                elk_logger.error("API request - server error", extra=context)
            elif status_code >= 400:
                elk_logger.warning("API request - client error", extra=context)
            elif duration > 2.0:  # Slow request
                elk_logger.warning("API request - slow response", extra=context)
            else:
                elk_logger.info("API request completed", extra=context)
                
        except Exception as e:
            # Don't break the request if ELK logging fails
            api_metrics_logger.debug(f"ELK logging failed: {e}")

    def _record_prometheus_metrics(self, method, endpoint, status_code, user_tier, duration):
        """EXISTING: Safely record to Prometheus without circular imports."""
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
        """EXISTING: Extract user tier for Prometheus (without the username)."""
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
                return 'admin' if user.is_superuser else 'free'
            else:
                return 'anonymous'
        except:
            return 'unknown'
    
    def process_exception(self, request, exception):
        """Enhanced exception logging with ELK context."""
        if not self._is_api_request(request):
            return None
            
        try:
            start_time = getattr(request, '_start_time', time.time())
            duration = time.time() - start_time
            
            method = request.method.upper()
            path = request.path_info
            user_info = self._get_user_info(request)
            endpoint = self._get_endpoint_name(request)
            
            # Log to api_metrics
            api_metrics_logger.error(
                f"API_METRIC method={method} endpoint={endpoint} "
                f"status=500 duration={duration:.3f}s "
                f"user={user_info} path={path} "
                f"exception={type(exception).__name__}"
            )
            
            # ELK structured error logging
            if ELK_AVAILABLE:
                user = getattr(request, 'user', None) if hasattr(request, 'user') else None
                context = create_log_context(request=request, user=user)
                context.update({
                    'event_type': EventTypes.API_ERROR,
                    'endpoint': endpoint,
                    'status_code': 500,
                    'duration': round(duration, 3),
                    'error_type': type(exception).__name__,
                    'error_message': str(exception),
                    'stack_trace': self._get_stack_trace(exception)
                })
                
                elk_logger.error("API exception occurred", extra=context)
            
        except Exception as e:
            api_metrics_logger.error(f"Exception metrics logging failed: {e}")
            
        return None
    
    def _get_stack_trace(self, exception):
        """Get formatted stack trace for logging."""
        try:
            import traceback
            return traceback.format_exception(type(exception), exception, exception.__traceback__)
        except:
            return f"Stack trace unavailable: {str(exception)}"
    
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