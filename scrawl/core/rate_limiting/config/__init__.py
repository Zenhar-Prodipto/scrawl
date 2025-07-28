# scrawl/core/rate_limiting/config/__init__.py
"""Rate limiting configuration for Scrawl application."""

from .limits import RateLimitConfig, rate_limit_config

__all__ = [
    'RateLimitConfig',
    'rate_limit_config',
]