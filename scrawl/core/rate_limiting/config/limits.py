"""
Centralized rate limiting configuration for Scrawl application.
Defines all rate limits in one place for easy management and updates.
"""
import os
from typing import Dict, Any, Optional
from django.conf import settings


class RateLimitConfig:
    """
    Centralized configuration for all rate limiting settings.
    Supports environment-based overrides and dynamic configuration.
    """
    
    def __init__(self):
        self._config_cache = {}
        self._environment = self._get_environment()
    
    def _get_environment(self) -> str:
        """Get current environment (local, development, staging, production)."""
        return getattr(settings, 'ENVIRONMENT', 'local').lower()
    
    # =====================================
    # USER-BASED RATE LIMITS
    # =====================================
    
    def get_user_rate_limits(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """
        Get user-based rate limits by tier and action.
        Production-grade limits based on industry standards.
        
        Returns:
            Nested dictionary: {tier: {action: {limit, window, burst_size}}}
        """
        base_limits = {
            'free': {
                # API access - Twitter allows ~300 requests per 15min = 1200/hour
                'api_call': {
                    'limit': self._get_env_override('USER_API_LIMIT_FREE', 1000),
                    'window': 3600,  # 1 hour
                    'burst_size': 1200,
                },
                
                # Profile management - Conservative for free users
                'profile_update': {
                    'limit': self._get_env_override('USER_PROFILE_LIMIT_FREE', 5),
                    'window': 3600,  # 5 updates per hour
                    'burst_size': 8,
                },
                'interest_update': {
                    'limit': self._get_env_override('USER_INTEREST_LIMIT_FREE', 20),
                    'window': 3600,  # 20 interest changes per hour
                    'burst_size': 30,
                },
                'profile_view': {
                    'limit': self._get_env_override('USER_PROFILE_VIEW_LIMIT_FREE', 100),
                    'window': 3600,  # 100 profile views per hour
                    'burst_size': 150,
                },
                'logout': {
                    'limit': self._get_env_override('USER_LOGOUT_LIMIT_FREE', 10),
                    'window': 3600,  # 10 logouts per hour (reasonable)
                    'burst_size': 15,
                },
                
                # Follow operations - Based on Instagram/Twitter patterns
                'follow': {
                    'limit': self._get_env_override('USER_FOLLOW_LIMIT_FREE', 60),
                    'window': 3600,  # Instagram allows ~60 follows/hour
                    'burst_size': 80,
                },
                'followers_view': {
                    'limit': self._get_env_override('USER_FOLLOWERS_VIEW_LIMIT_FREE', 200),
                    'window': 3600,  # 200 follower list views per hour
                    'burst_size': 250,
                },
                'following_view': {
                    'limit': self._get_env_override('USER_FOLLOWING_VIEW_LIMIT_FREE', 200),
                    'window': 3600,  # 200 following list views per hour
                    'burst_size': 250,
                },
                'follow_status': {
                    'limit': self._get_env_override('USER_FOLLOW_STATUS_LIMIT_FREE', 300),
                    'window': 3600,  # Check follow status frequently
                    'burst_size': 400,
                },
                'pending_follow_requests_incoming': {
                    'limit': self._get_env_override('USER_PENDING_FOLLOW_REQUESTS_INCOMING_LIMIT_FREE', 50),
                    'window': 3600,  # Check incoming requests
                    'burst_size': 75,
                },
                'pending_follow_requests_outgoing': {
                    'limit': self._get_env_override('USER_PENDING_FOLLOW_REQUESTS_OUTGOING_LIMIT_FREE', 50),
                    'window': 3600,  # Check outgoing requests
                    'burst_size': 75,
                },
                'follow_request_update': {
                    'limit': self._get_env_override('USER_FOLLOW_REQUEST_UPDATE_LIMIT_FREE', 100),
                    'window': 3600,  # Accept/deny requests
                    'burst_size': 150,
                },
                'follow_request_cancel': {
                    'limit': self._get_env_override('USER_FOLLOW_REQUEST_CANCEL_LIMIT_FREE', 50),
                    'window': 3600,  # Cancel outgoing requests
                    'burst_size': 75,
                },
                
                # Post operations - Social media standard limits
                'post_create': {
                    'limit': self._get_env_override('USER_POST_CREATE_LIMIT_FREE', 25),
                    'window': 3600,  # 25 posts per hour 
                    'burst_size': 35,
                },
                'comment_post': {
                    'limit': self._get_env_override('USER_COMMENT_POST_LIMIT_FREE', 100),
                    'window': 3600,  # 100 comments per hour
                    'burst_size': 150,
                },
                'like_post': {
                    'limit': self._get_env_override('USER_LIKE_POST_LIMIT_FREE', 300),
                    'window': 3600,  # 300 likes per hour 
                    'burst_size': 400,
                },
                'save_post': {
                    'limit': self._get_env_override('USER_SAVE_POST_LIMIT_FREE', 150),
                    'window': 3600,  # 150 saves per hour
                    'burst_size': 200,
                },
                'post_update': {
                    'limit': self._get_env_override('USER_POST_UPDATE_LIMIT_FREE', 20),
                    'window': 3600,  # 20 post edits per hour
                    'burst_size': 30,
                },
                'post_delete': {
                    'limit': self._get_env_override('USER_POST_DELETE_LIMIT_FREE', 10),
                    'window': 3600,  # 10 post deletions per hour
                    'burst_size': 15,
                },
                'post_list_view': {
                    'limit': self._get_env_override('USER_LIST_LIMIT_FREE', 200),
                    'window': 3600,  # 200 post list views per hour
                    'burst_size': 300,
                },
                'post_view': {
                    'limit': self._get_env_override('USER_POST_VIEW_LIMIT_FREE', 500),
                    'window': 3600,  # 500 individual post views per hour
                    'burst_size': 700,
                },
                'saved_posts_view': {
                    'limit': self._get_env_override('USER_SAVED_POSTS_VIEW_LIMIT_FREE', 100),
                    'window': 3600,  # 100 saved posts views per hour
                    'burst_size': 150,
                },
                'user_posts_view': {
                    'limit': self._get_env_override('USER_POSTS_VIEW_LIMIT_FREE', 150),
                    'window': 3600,  # 150 user profile post views per hour
                    'burst_size': 200,
                },
                'user_post_view_details': {
                    'limit': self._get_env_override('USER_POST_VIEW_DETAILS_LIMIT_FREE', 200),
                    'window': 3600,  # 200 detailed post views per hour
                    'burst_size': 300,
                },
                
                # Feed - Expensive operation, limit accordingly
                'feed_request': {
                    'limit': self._get_env_override('USER_FEED_LIMIT_FREE', 60),
                    'window': 3600,  # 60 feed refreshes per hour (1 per minute)
                    'burst_size': 90,
                },
            },
            
            'premium': {
                # API access - 2.5x increase for premium
                'api_call': {
                    'limit': self._get_env_override('USER_API_LIMIT_PREMIUM', 2500),
                    'window': 3600,
                    'burst_size': 3000,
                },
                
                # Profile management - Higher limits
                'profile_update': {
                    'limit': self._get_env_override('USER_PROFILE_LIMIT_PREMIUM', 15),
                    'window': 3600,
                    'burst_size': 25,
                },
                'interest_update': {
                    'limit': self._get_env_override('USER_INTEREST_LIMIT_PREMIUM', 50),
                    'window': 3600,
                    'burst_size': 75,
                },
                'profile_view': {
                    'limit': self._get_env_override('USER_PROFILE_VIEW_LIMIT_PREMIUM', 300),
                    'window': 3600,
                    'burst_size': 400,
                },
                'logout': {
                    'limit': self._get_env_override('USER_LOGOUT_LIMIT_PREMIUM', 20),
                    'window': 3600,
                    'burst_size': 30,
                },
                
                # Follow operations - Premium gets higher limits
                'follow': {
                    'limit': self._get_env_override('USER_FOLLOW_LIMIT_PREMIUM', 120),
                    'window': 3600,  # 2x free tier
                    'burst_size': 150,
                },
                'followers_view': {
                    'limit': self._get_env_override('USER_FOLLOWERS_VIEW_LIMIT_PREMIUM', 500),
                    'window': 3600,
                    'burst_size': 600,
                },
                'following_view': {
                    'limit': self._get_env_override('USER_FOLLOWING_VIEW_LIMIT_PREMIUM', 500),
                    'window': 3600,
                    'burst_size': 600,
                },
                'follow_status': {
                    'limit': self._get_env_override('USER_FOLLOW_STATUS_LIMIT_PREMIUM', 600),
                    'window': 3600,
                    'burst_size': 750,
                },
                'pending_follow_requests_incoming': {
                    'limit': self._get_env_override('USER_PENDING_FOLLOW_REQUESTS_INCOMING_LIMIT_PREMIUM', 100),
                    'window': 3600,
                    'burst_size': 150,
                },
                'pending_follow_requests_outgoing': {
                    'limit': self._get_env_override('USER_PENDING_FOLLOW_REQUESTS_OUTGOING_LIMIT_PREMIUM', 100),
                    'window': 3600,
                    'burst_size': 150,
                },
                'follow_request_update': {
                    'limit': self._get_env_override('USER_FOLLOW_REQUEST_UPDATE_LIMIT_PREMIUM', 200),
                    'window': 3600,
                    'burst_size': 300,
                },
                'follow_request_cancel': {
                    'limit': self._get_env_override('USER_FOLLOW_REQUEST_CANCEL_LIMIT_PREMIUM', 100),
                    'window': 3600,
                    'burst_size': 150,
                },
                
                # Post operations - Premium benefits
                'post_create': {
                    'limit': self._get_env_override('USER_POST_CREATE_LIMIT_PREMIUM', 60),
                    'window': 3600,  # 60 posts per hour
                    'burst_size': 80,
                },
                'comment_post': {
                    'limit': self._get_env_override('USER_COMMENT_POST_LIMIT_PREMIUM', 300),
                    'window': 3600,
                    'burst_size': 400,
                },
                'like_post': {
                    'limit': self._get_env_override('USER_LIKE_POST_LIMIT_PREMIUM', 800),
                    'window': 3600,
                    'burst_size': 1000,
                },
                'save_post': {
                    'limit': self._get_env_override('USER_SAVE_POST_LIMIT_PREMIUM', 400),
                    'window': 3600,
                    'burst_size': 500,
                },
                'post_update': {
                    'limit': self._get_env_override('USER_POST_UPDATE_LIMIT_PREMIUM', 50),
                    'window': 3600,
                    'burst_size': 75,
                },
                'post_delete': {
                    'limit': self._get_env_override('USER_POST_DELETE_LIMIT_PREMIUM', 25),
                    'window': 3600,
                    'burst_size': 40,
                },
                'post_list_view': {
                    'limit': self._get_env_override('USER_LIST_LIMIT_PREMIUM', 500),
                    'window': 3600,
                    'burst_size': 700,
                },
                'post_view': {
                    'limit': self._get_env_override('USER_POST_VIEW_LIMIT_PREMIUM', 1200),
                    'window': 3600,
                    'burst_size': 1500,
                },
                'saved_posts_view': {
                    'limit': self._get_env_override('USER_SAVED_POSTS_VIEW_LIMIT_PREMIUM', 300),
                    'window': 3600,
                    'burst_size': 400,
                },
                'user_posts_view': {
                    'limit': self._get_env_override('USER_POSTS_VIEW_LIMIT_PREMIUM', 400),
                    'window': 3600,
                    'burst_size': 500,
                },
                'user_post_view_details': {
                    'limit': self._get_env_override('USER_POST_VIEW_DETAILS_LIMIT_PREMIUM', 500),
                    'window': 3600,
                    'burst_size': 700,
                },
                
                # Feed - Premium gets more feed refreshes
                'feed_request': {
                    'limit': self._get_env_override('USER_FEED_LIMIT_PREMIUM', 150),
                    'window': 3600,  # 150 feed refreshes per hour
                    'burst_size': 200,
                },
            },
            
            'admin': {
                # API access - Very high limits for admin operations
                'api_call': {
                    'limit': self._get_env_override('USER_API_LIMIT_ADMIN', 10000),
                    'window': 3600,
                    'burst_size': 15000,
                },
                
                # Profile management - Admin can do bulk operations
                'profile_update': {
                    'limit': self._get_env_override('USER_PROFILE_LIMIT_ADMIN', 100),
                    'window': 3600,
                    'burst_size': 150,
                },
                'interest_update': {
                    'limit': self._get_env_override('USER_INTEREST_LIMIT_ADMIN', 200),
                    'window': 3600,
                    'burst_size': 300,
                },
                'profile_view': {
                    'limit': self._get_env_override('USER_PROFILE_VIEW_LIMIT_ADMIN', 1000),
                    'window': 3600,
                    'burst_size': 1500,
                },
                'logout': {
                    'limit': self._get_env_override('USER_LOGOUT_LIMIT_ADMIN', 50),
                    'window': 3600,
                    'burst_size': 75,
                },
                
                # Follow operations - Admin needs high limits for moderation
                'follow': {
                    'limit': self._get_env_override('USER_FOLLOW_LIMIT_ADMIN', 500),
                    'window': 3600,
                    'burst_size': 750,
                },
                'followers_view': {
                    'limit': self._get_env_override('USER_FOLLOWERS_VIEW_LIMIT_ADMIN', 2000),
                    'window': 3600,
                    'burst_size': 3000,
                },
                'following_view': {
                    'limit': self._get_env_override('USER_FOLLOWING_VIEW_LIMIT_ADMIN', 2000),
                    'window': 3600,
                    'burst_size': 3000,
                },
                'follow_status': {
                    'limit': self._get_env_override('USER_FOLLOW_STATUS_LIMIT_ADMIN', 2000),
                    'window': 3600,
                    'burst_size': 3000,
                },
                'pending_follow_requests_incoming': {
                    'limit': self._get_env_override('USER_PENDING_FOLLOW_REQUESTS_INCOMING_LIMIT_ADMIN', 500),
                    'window': 3600,
                    'burst_size': 750,
                },
                'pending_follow_requests_outgoing': {
                    'limit': self._get_env_override('USER_PENDING_FOLLOW_REQUESTS_OUTGOING_LIMIT_ADMIN', 500),
                    'window': 3600,
                    'burst_size': 750,
                },
                'follow_request_update': {
                    'limit': self._get_env_override('USER_FOLLOW_REQUEST_UPDATE_LIMIT_ADMIN', 1000),
                    'window': 3600,
                    'burst_size': 1500,
                },
                'follow_request_cancel': {
                    'limit': self._get_env_override('USER_FOLLOW_REQUEST_CANCEL_LIMIT_ADMIN', 500),
                    'window': 3600,
                    'burst_size': 750,
                },
                
                # Post operations - High limits for content moderation
                'post_create': {
                    'limit': self._get_env_override('USER_POST_CREATE_LIMIT_ADMIN', 200),
                    'window': 3600,
                    'burst_size': 300,
                },
                'comment_post': {
                    'limit': self._get_env_override('USER_COMMENT_POST_LIMIT_ADMIN', 1000),
                    'window': 3600,
                    'burst_size': 1500,
                },
                'like_post': {
                    'limit': self._get_env_override('USER_LIKE_POST_LIMIT_ADMIN', 2000),
                    'window': 3600,
                    'burst_size': 3000,
                },
                'save_post': {
                    'limit': self._get_env_override('USER_SAVE_POST_LIMIT_ADMIN', 1000),
                    'window': 3600,
                    'burst_size': 1500,
                },
                'post_update': {
                    'limit': self._get_env_override('USER_POST_UPDATE_LIMIT_ADMIN', 200),
                    'window': 3600,
                    'burst_size': 300,
                },
                'post_delete': {
                    'limit': self._get_env_override('USER_POST_DELETE_LIMIT_ADMIN', 100),
                    'window': 3600,
                    'burst_size': 150,
                },
                'post_list_view': {
                    'limit': self._get_env_override('USER_LIST_LIMIT_ADMIN', 2000),
                    'window': 3600,
                    'burst_size': 3000,
                },
                'post_view': {
                    'limit': self._get_env_override('USER_POST_VIEW_LIMIT_ADMIN', 5000),
                    'window': 3600,
                    'burst_size': 7500,
                },
                'saved_posts_view': {
                    'limit': self._get_env_override('USER_SAVED_POSTS_VIEW_LIMIT_ADMIN', 1000),
                    'window': 3600,
                    'burst_size': 1500,
                },
                'user_posts_view': {
                    'limit': self._get_env_override('USER_POSTS_VIEW_LIMIT_ADMIN', 1500),
                    'window': 3600,
                    'burst_size': 2000,
                },
                'user_post_view_details': {
                    'limit': self._get_env_override('USER_POST_VIEW_DETAILS_LIMIT_ADMIN', 2000),
                    'window': 3600,
                    'burst_size': 3000,
                },
                
                # Feed - Admin needs unlimited feed access for monitoring
                'feed_request': {
                    'limit': self._get_env_override('USER_FEED_LIMIT_ADMIN', 1000),
                    'window': 3600,
                    'burst_size': 1500,
                },
            }
        }
        
        # Remove debug prints for production
        return self._apply_environment_adjustments(base_limits, 'user')

    # =====================================
    # IP-BASED RATE LIMITS
    # =====================================
    def get_ip_rate_limits(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """
        Get IP-based rate limits by category and action.
        Production-grade IP limits for security and performance.
        
        Returns:
            Nested dictionary: {ip_category: {action: {limit, window}}}
        """
        base_limits = {
            'trusted': {
                'request': {
                    'limit': self._get_env_override('IP_REQUEST_LIMIT_TRUSTED', 10000),
                    'window': 3600,  # 10k requests/hour from trusted IPs
                },
                'login': {
                    'limit': self._get_env_override('IP_LOGIN_LIMIT_TRUSTED', 100),
                    'window': 3600,  # 100 login attempts/hour from trusted
                },
                'register': {
                    'limit': self._get_env_override('IP_REGISTER_LIMIT_TRUSTED', 10),
                    'window': 86400,  # 10 registrations/day from trusted
                },
                'password_reset': {
                    'limit': self._get_env_override('IP_RESET_LIMIT_TRUSTED', 50),
                    'window': 3600,  # 50 password resets/hour
                },
                'api_call': {
                    'limit': self._get_env_override('IP_API_LIMIT_TRUSTED', 8000),
                    'window': 3600,  # High API limits for trusted
                },
            },
            
            'local': {
                'request': {
                    'limit': self._get_env_override('IP_REQUEST_LIMIT_LOCAL', 5000),
                    'window': 3600,  # 5k requests/hour from local
                },
                'login': {
                    'limit': self._get_env_override('IP_LOGIN_LIMIT_LOCAL', 50),
                    'window': 3600,  # 50 login attempts/hour local
                },
                'register': {
                    'limit': self._get_env_override('IP_REGISTER_LIMIT_LOCAL', 5),
                    'window': 86400,  # 5 registrations/day local
                },
                'password_reset': {
                    'limit': self._get_env_override('IP_RESET_LIMIT_LOCAL', 20),
                    'window': 3600,  # 20 password resets/hour
                },
                'api_call': {
                    'limit': self._get_env_override('IP_API_LIMIT_LOCAL', 4000),
                    'window': 3600,  # Good API limits for local
                },
            },
            
            'public': {
                'request': {
                    'limit': self._get_env_override('IP_REQUEST_LIMIT_PUBLIC', 2000),
                    'window': 3600,  # 2k requests/hour from public IPs
                },
                'login': {
                    'limit': self._get_env_override('IP_LOGIN_LIMIT_PUBLIC', 20),
                    'window': 3600,  # 20 login attempts/hour (anti-brute force)
                },
                'register': {
                    'limit': self._get_env_override('IP_REGISTER_LIMIT_PUBLIC', 3),
                    'window': 86400,  # 3 registrations/day (anti-spam)
                },
                'password_reset': {
                    'limit': self._get_env_override('IP_RESET_LIMIT_PUBLIC', 10),
                    'window': 3600,  # 10 password resets/hour
                },
                'api_call': {
                    'limit': self._get_env_override('IP_API_LIMIT_PUBLIC', 1500),
                    'window': 3600,  # Reasonable API limits for public
                },
            },
            
            'blocked': {
                'request': {
                    'limit': self._get_env_override('IP_REQUEST_LIMIT_BLOCKED', 10),
                    'window': 3600,  # Very low for blocked IPs
                },
                'login': {
                    'limit': self._get_env_override('IP_LOGIN_LIMIT_BLOCKED', 1),
                    'window': 3600,  # 1 login attempt/hour for blocked
                },
                'register': {
                    'limit': self._get_env_override('IP_REGISTER_LIMIT_BLOCKED', 0),
                    'window': 86400,  # No registrations for blocked IPs
                },
                'password_reset': {
                    'limit': self._get_env_override('IP_RESET_LIMIT_BLOCKED', 1),
                    'window': 3600,  # 1 password reset/hour
                },
                'api_call': {
                    'limit': self._get_env_override('IP_API_LIMIT_BLOCKED', 5),
                    'window': 3600,  # Minimal API access for blocked
                },
            }
        }
    
        return self._apply_environment_adjustments(base_limits, 'ip')
    
    # =====================================
    # ENDPOINT-SPECIFIC RATE LIMITS
    # =====================================
    
    def get_endpoint_rate_limits(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """
        Get endpoint-specific rate limits by endpoint and HTTP method.
        
        Returns:
            Nested dictionary: {endpoint: {method: {limit, window}}}
        """
        base_limits = {
            # Feed endpoints (expensive)
            'feed.feed': {
                'GET': {
                    'limit': self._get_env_override('ENDPOINT_FEED_LIMIT', 60),
                    'window': 3600,
                },
            },
            
            # Post endpoints
            'posts.create-post': {
                'POST': {
                    'limit': self._get_env_override('ENDPOINT_POST_CREATE_LIMIT', 10),
                    'window': 3600,
                },
            },
            'posts.post-detail': {
                'GET': {
                    'limit': self._get_env_override('ENDPOINT_POST_VIEW_LIMIT', 200),
                    'window': 3600,
                },
                'PATCH': {
                    'limit': self._get_env_override('ENDPOINT_POST_UPDATE_LIMIT', 20),
                    'window': 3600,
                },
                'DELETE': {
                    'limit': self._get_env_override('ENDPOINT_POST_DELETE_LIMIT', 10),
                    'window': 3600,
                },
            },
            'posts.like-post': {
                'POST': {
                    'limit': self._get_env_override('ENDPOINT_LIKE_LIMIT', 200),
                    'window': 3600,
                },
                'DELETE': {
                    'limit': self._get_env_override('ENDPOINT_UNLIKE_LIMIT', 200),
                    'window': 3600,
                },
            },
            'posts.comment-post': {
                'POST': {
                    'limit': self._get_env_override('ENDPOINT_COMMENT_CREATE_LIMIT', 50),
                    'window': 3600,
                },
                'PATCH': {
                    'limit': self._get_env_override('ENDPOINT_COMMENT_UPDATE_LIMIT', 30),
                    'window': 3600,
                },
                'DELETE': {
                    'limit': self._get_env_override('ENDPOINT_COMMENT_DELETE_LIMIT', 30),
                    'window': 3600,
                },
            },
            
            # Follow endpoints
            'follows.follow-unfollow': {
                'POST': {
                    'limit': self._get_env_override('ENDPOINT_FOLLOW_LIMIT', 20),
                    'window': 3600,
                },
                'DELETE': {
                    'limit': self._get_env_override('ENDPOINT_UNFOLLOW_LIMIT', 20),
                    'window': 3600,
                },
            },
            
            # User endpoints
            'users.register': {
                'POST': {
                    'limit': self._get_env_override('ENDPOINT_REGISTER_LIMIT', 5),
                    'window': 86400,
                },
            },
            'users.login': {
                'POST': {
                    'limit': self._get_env_override('ENDPOINT_LOGIN_LIMIT', 30),
                    'window': 3600,
                },
            },
            
            # Default limits for unspecified endpoints
            '_default': {
                'GET': {
                    'limit': self._get_env_override('ENDPOINT_DEFAULT_GET_LIMIT', 500),
                    'window': 3600,
                },
                'POST': {
                    'limit': self._get_env_override('ENDPOINT_DEFAULT_POST_LIMIT', 100),
                    'window': 3600,
                },
                'PATCH': {
                    'limit': self._get_env_override('ENDPOINT_DEFAULT_PATCH_LIMIT', 100),
                    'window': 3600,
                },
                'PUT': {
                    'limit': self._get_env_override('ENDPOINT_DEFAULT_PUT_LIMIT', 100),
                    'window': 3600,
                },
                'DELETE': {
                    'limit': self._get_env_override('ENDPOINT_DEFAULT_DELETE_LIMIT', 50),
                    'window': 3600,
                },
            }
        }
        
        return self._apply_environment_adjustments(base_limits, 'endpoint')
    
    # =====================================
    # ALGORITHM CONFIGURATIONS
    # =====================================
    
    def get_algorithm_defaults(self) -> Dict[str, str]:
        """
        Get default algorithms for different rate limiter types.
        
        Returns:
            Dictionary mapping limiter types to algorithms
        """
        return {
            'user': self._get_env_override('ALGORITHM_USER', 'token_bucket'),
            'ip': self._get_env_override('ALGORITHM_IP', 'sliding_window'),
            'endpoint': self._get_env_override('ALGORITHM_ENDPOINT', 'fixed_window'),
        }
    
    # =====================================
    # UTILITY METHODS
    # =====================================
    
    def _get_env_override(self, key: str, default: Any) -> Any:
        """
        Get environment variable override for configuration values.
        
        Args:
            key: Environment variable key
            default: Default value if not set
            
        Returns:
            Environment value or default
        """
        env_value = os.getenv(f'RATE_LIMIT_{key}')
        if env_value is not None:
            # Try to convert to appropriate type
            if isinstance(default, int):
                try:
                    return int(env_value)
                except (ValueError, TypeError):
                    pass
            elif isinstance(default, float):
                try:
                    return float(env_value)
                except (ValueError, TypeError):
                    pass
            elif isinstance(default, bool):
                return env_value.lower() in ('true', '1', 'yes', 'on')
            return env_value
        return default
    
    def _apply_environment_adjustments(self, limits: Dict, limit_type: str) -> Dict:
        """
        Apply environment-specific adjustments to rate limits.
        
        Args:
            limits: Base rate limits
            limit_type: Type of limits ('user', 'ip', 'endpoint')
            
        Returns:
            Adjusted limits based on environment
        """
        
        print(f"🔍 DEBUG: Environment = {self._environment}", flush=True)
        print(f"🔍 DEBUG: BEFORE adjustments: profile_update = {limits.get('free', {}).get('profile_update', 'NOT FOUND')}", flush=True)
        if self._environment == 'local':
            # Higher limits for local development
            # return limits
            return self._multiply_limits(limits, 2.0)
        elif self._environment == 'development':
            # Slightly higher limits for development
            return self._multiply_limits(limits, 1.5)
        elif self._environment == 'staging':
            # Standard limits for staging
            return limits
        elif self._environment == 'production':
            # Potentially stricter limits for production
            production_multiplier = self._get_env_override('PRODUCTION_LIMIT_MULTIPLIER', 1.0)
            return self._multiply_limits(limits, production_multiplier)
        else:
            adjusted = limits

        print(f"🔍 DEBUG: AFTER adjustments: profile_update = {adjusted.get('free', {}).get('profile_update', 'NOT FOUND')}", flush=True)
    
        return limits
    
    def _multiply_limits(self, limits: Dict, multiplier: float) -> Dict:
        """
        Multiply all limit values by a factor.
        
        Args:
            limits: Rate limits dictionary
            multiplier: Multiplication factor
            
        Returns:
            Limits with multiplied values
        """
        if multiplier == 1.0:
            return limits
        
        adjusted = {}
        for key, value in limits.items():
            if isinstance(value, dict):
                adjusted[key] = self._multiply_limits(value, multiplier)
            elif key == 'limit':
                adjusted[key] = max(1, int(value * multiplier))
            elif key == 'burst_size':
                adjusted[key] = max(1, int(value * multiplier))
            else:
                adjusted[key] = value
        
        return adjusted
    
    def get_trusted_ip_networks(self) -> list[str]:
        """
        Get list of trusted IP networks.
        
        Returns:
            List of CIDR network strings
        """
        default_networks = [
            '127.0.0.0/8',      # Localhost
            '10.0.0.0/8',       # Private network
            '172.16.0.0/12',    # Private network
            '192.168.0.0/16',   # Private network
        ]
        
        # Allow environment override
        env_networks = os.getenv('RATE_LIMIT_TRUSTED_NETWORKS')
        if env_networks:
            return env_networks.split(',')
        
        return default_networks
    
    def get_blocked_ip_networks(self) -> list[str]:
        """
        Get list of blocked IP networks.
        
        Returns:
            List of CIDR network strings
        """
        # Load from environment or external service
        env_networks = os.getenv('RATE_LIMIT_BLOCKED_NETWORKS')
        if env_networks:
            return env_networks.split(',')
        
        return []  # No blocked networks by default
    
    def is_rate_limiting_enabled(self) -> bool:
        """
        Check if rate limiting is globally enabled.
        
        Returns:
            True if rate limiting should be active
        """
        return self._get_env_override('ENABLED', True)
    
    def get_redis_key_prefix(self) -> str:
        """
        Get Redis key prefix for rate limiting.
        
        Returns:
            Key prefix string
        """
        return self._get_env_override('REDIS_KEY_PREFIX', 'rate_limit')


# Global configuration instance
rate_limit_config = RateLimitConfig()