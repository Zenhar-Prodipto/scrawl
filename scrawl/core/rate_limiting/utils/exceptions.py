"""
Custom exceptions for Scrawl rate limiting system.
Provides specific exception types for different rate limiting scenarios.
"""
from rest_framework.exceptions import Throttled
from rest_framework import status


class RateLimitExceeded(Throttled):
    """
    Base exception for all rate limit violations.
    Extends DRF's Throttled for consistent API responses.
    """
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Rate limit exceeded. Please try again later.'
    default_code = 'rate_limit_exceeded'
    
    def __init__(self, detail=None, wait=None, limit_type=None, limit_value=None):
        super().__init__(detail, wait)
        self.limit_type = limit_type
        self.limit_value = limit_value


class UserRateLimitExceeded(RateLimitExceeded):
    """Exception for user-based rate limit violations."""
    default_detail = 'User rate limit exceeded. You have made too many requests.'
    default_code = 'user_rate_limit_exceeded'


class IPRateLimitExceeded(RateLimitExceeded):
    """Exception for IP-based rate limit violations."""
    default_detail = 'IP rate limit exceeded. Too many requests from your IP address.'
    default_code = 'ip_rate_limit_exceeded'


class EndpointRateLimitExceeded(RateLimitExceeded):
    """Exception for endpoint-specific rate limit violations."""
    default_detail = 'Endpoint rate limit exceeded. This action is temporarily restricted.'
    default_code = 'endpoint_rate_limit_exceeded'


class RateLimitConfigurationError(Exception):
    """Exception for rate limiting configuration errors."""
    pass


class RateLimitBackendError(Exception):
    """Exception for rate limiting backend errors (Redis connection, etc.)."""
    pass