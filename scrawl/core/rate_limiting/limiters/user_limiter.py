"""
User-based rate limiter for Scrawl application.
Prevents spam and abuse by limiting actions per authenticated user.
"""
import logging
from typing import Dict, Any, Optional
from django.http import HttpRequest
from .base_limiter import BaseRateLimiter
from ..utils.exceptions import UserRateLimitExceeded

logger = logging.getLogger(__name__)


class UserRateLimiter(BaseRateLimiter):
    """
    Rate limiter based on authenticated user.
    Perfect for preventing spam posts, excessive follows, and content abuse.
    """
    
    def __init__(self, action_type: str = 'api_call', algorithm: str = 'token_bucket', backend=None):
        """
        Initialize user rate limiter.
        
        Args:
            action_type: Type of action being limited (e.g., 'post', 'follow', 'like')
            algorithm: Rate limiting algorithm (token_bucket recommended for social media)
            backend: Rate limiting backend
        """
        super().__init__(algorithm, backend)
        self.action_type = action_type
    
    def get_rate_limit_key(self, request: HttpRequest, view: Any = None) -> str:
        """
        Generate rate limit key based on user and action type.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Rate limit key: 'rate_limit:user:{user_id}:{action_type}'
        """
        # Check if user is authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            logger.warning("User rate limiter called for unauthenticated request")
            return None
        
        user_id = request.user.id
        return f"rate_limit:user:{user_id}:{self.action_type}"
    
    def get_rate_limit_config(self, request: HttpRequest, view: Any = None) -> Dict[str, int]:
        """
        Get rate limit configuration based on user type and action.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Dictionary with rate limit configuration
        """
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return {}
        
        user = request.user
        
        # Get user tier for tiered rate limiting
        user_tier = self._get_user_tier(user)
        
        # Action-specific rate limits
        rate_limits = self._get_action_rate_limits(user_tier)
        
        print(f"🔍 DEBUG: Raw rate_limits for {user_tier} = {rate_limits}", flush=True)
    
        config = rate_limits.get(self.action_type, {})
        print(f"🔍 DEBUG: Extracted config for {self.action_type} = {config}", flush=True)
        print(f"🔍 DEBUG ALGORITHM: UserRateLimiter using algorithm = {self.algorithm}", flush=True)
        
        return config
    
    def _get_user_tier(self, user) -> str:
        """
        Determine user tier for tiered rate limiting.
        
        Args:
            user: Django user object
            
        Returns:
            User tier string ('free', 'premium', 'admin')
        """
        # Check if user is admin/staff
        if user.is_staff or user.is_superuser:
            return 'admin'
        
        # TODO: Add premium user logic based on business model
        # For now, all users are 'free' tier
        # This can be extended to this with:
        # - Premium subscription checks
        # - User account age
        # - Verification status
        # - Special privileges
        
        return 'free'
    
    def _get_action_rate_limits(self, user_tier: str) -> Dict[str, Dict[str, int]]:
        """
        Get rate limits by action type and user tier from centralized config.
        """
        # Import here to avoid circular imports
        from ..config.limits import rate_limit_config
        
        # Get centralized user rate limits
        user_limits = rate_limit_config.get_user_rate_limits()
        print(f"🔍 DEBUG: User limits = {user_limits}", flush=True)
        
        # Return limits for the user tier (fallback to 'free' if tier not found)
        return user_limits.get(user_tier, user_limits.get('free', {}))
    
    def get_exception_class(self):
        """Return user-specific rate limit exception."""
        return UserRateLimitExceeded
    
    def is_user_exempt(self, user) -> bool:
        """
        Check if user is exempt from rate limiting.
        
        Args:
            user: Django user object
            
        Returns:
            True if user should be exempt from rate limits
        """
        # Exempt superusers for emergency access
        if user.is_superuser:
            return True
        
        # TODO: Add other exemption logic:
        # - Verified accounts
        # - Special partnerships
        # - Testing accounts
        
        return False
    
    def is_allowed(self, request: HttpRequest, view: Any = None) -> tuple[bool, Dict[str, Any]]:
        """
        Check if user request is allowed, with exemption support.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        # Check user authentication
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            logger.warning(f"User rate limiter applied to unauthenticated request: {request.path}")
            return True, {'reason': 'unauthenticated'}
        
        # Check if user is exempt
        if self.is_user_exempt(request.user):
            logger.debug(f"User {request.user.id} exempt from {self.action_type} rate limiting")
            return True, {'reason': 'exempt', 'user_tier': self._get_user_tier(request.user)}
        
        # Perform normal rate limit check
        return super().is_allowed(request, view)
    
    def get_rate_limit_headers(self, request: HttpRequest, metadata: Dict[str, Any]) -> Dict[str, str]:
        """
        Get HTTP headers for rate limit information.
        
        Args:
            request: Django HTTP request
            metadata: Rate limit metadata
            
        Returns:
            Dictionary of HTTP headers
        """
        headers = {}
        
        if 'remaining' in metadata:
            headers['X-RateLimit-Remaining'] = str(metadata['remaining'])
        
        if 'reset_time' in metadata:
            headers['X-RateLimit-Reset'] = str(metadata['reset_time'])
        
        if 'current_count' in metadata:
            headers['X-RateLimit-Used'] = str(metadata['current_count'])
        
        # Add user-specific headers
        if hasattr(request, 'user') and request.user.is_authenticated:
            headers['X-RateLimit-User-Tier'] = self._get_user_tier(request.user)
            headers['X-RateLimit-Action-Type'] = self.action_type
        
        return headers
    
    def __str__(self):
        """String representation of user rate limiter."""
        return f"UserRateLimiter(action={self.action_type}, algorithm={self.algorithm})"