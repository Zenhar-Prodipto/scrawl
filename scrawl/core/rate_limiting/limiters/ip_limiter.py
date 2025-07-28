"""
IP-based rate limiter for Scrawl application.
Prevents brute force attacks, DDoS, and infrastructure abuse.
"""
import logging
import ipaddress
from typing import Dict, Any, Optional, Set
from django.http import HttpRequest
from .base_limiter import BaseRateLimiter
from ..utils.exceptions import IPRateLimitExceeded

logger = logging.getLogger(__name__)


class IPRateLimiter(BaseRateLimiter):
    """
    Rate limiter based on client IP address.
    Essential for preventing brute force attacks and infrastructure abuse.
    """
    
    def __init__(self, action_type: str = 'request', algorithm: str = 'sliding_window', backend=None):
        """
        Initialize IP rate limiter.
        
        Args:
            action_type: Type of action being limited (e.g., 'login', 'register', 'request')
            algorithm: Rate limiting algorithm (sliding_window recommended for security)
            backend: Rate limiting backend
        """
        super().__init__(algorithm, backend)
        self.action_type = action_type
        
        # Trusted IP ranges that should have higher limits or be whitelisted
        self._trusted_networks = self._load_trusted_networks()
        
        # IP ranges that should be blocked entirely
        self._blocked_networks = self._load_blocked_networks()
    
    def get_rate_limit_key(self, request: HttpRequest, view: Any = None) -> str:
        """
        Generate rate limit key based on client IP and action type.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Rate limit key: 'rate_limit:ip:{ip_address}:{action_type}'
        """
        client_ip = self._get_client_ip(request)
        if not client_ip:
            logger.warning("Could not determine client IP for rate limiting")
            return None
        
        return f"rate_limit:ip:{client_ip}:{self.action_type}"
    
    def get_rate_limit_config(self, request: HttpRequest, view: Any = None) -> Dict[str, int]:
        """..."""
        client_ip = self._get_client_ip(request)
        if not client_ip:
            return {}
        
        # Determine IP category for different limits
        ip_category = self._categorize_ip(client_ip)
        print(f"🔍 DEBUG IP: client_ip={client_ip}, category={ip_category}", flush=True)
        
        # Get action-specific rate limits
        try:
            rate_limits = self._get_ip_rate_limits(ip_category)
            print(f"🔍 DEBUG IP: rate_limits={rate_limits}", flush=True)
            
            config = rate_limits.get(self.action_type, {})
            print(f"🔍 DEBUG IP: action={self.action_type}, config={config}", flush=True)
            
            return config
        except Exception as e:
            print(f"🔍 DEBUG IP: Exception in get_rate_limit_config: {e}", flush=True)
            import traceback
            print(f"🔍 DEBUG IP: Traceback: {traceback.format_exc()}", flush=True)
            return {}
    
    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """
        Extract client IP address from request headers.
        Handles proxy headers and load balancers.
        
        Args:
            request: Django HTTP request
            
        Returns:
            Client IP address string or None
        """
        # Check for IP in proxy headers (most common)
        ip_headers = [
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_REAL_IP',
            'HTTP_CF_CONNECTING_IP',  # Cloudflare
            'HTTP_X_FORWARDED',
            'HTTP_FORWARDED_FOR',
            'HTTP_FORWARDED',
            'REMOTE_ADDR',
        ]
        
        for header in ip_headers:
            ip = request.META.get(header)
            if ip:
                # Handle comma-separated IPs (X-Forwarded-For can have multiple IPs)
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                
                # Validate IP format
                if self._is_valid_ip(ip):
                    return ip
        
        return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """
        Validate IP address format.
        
        Args:
            ip: IP address string
            
        Returns:
            True if valid IP address
        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _categorize_ip(self, ip: str) -> str:
        """
        Categorize IP address for different rate limiting.
        
        Args:
            ip: IP address string
            
        Returns:
            IP category ('trusted', 'blocked', 'local', 'public')
        """
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            # Check if IP is in blocked networks
            if self._is_ip_in_networks(ip_obj, self._blocked_networks):
                return 'blocked'
            
            # Check if IP is in trusted networks
            if self._is_ip_in_networks(ip_obj, self._trusted_networks):
                return 'trusted'
            
            # Check if IP is local/private
            if ip_obj.is_private or ip_obj.is_loopback:
                return 'local'
            
            # Public IP
            return 'public'
            
        except ValueError:
            logger.warning(f"Invalid IP address for categorization: {ip}")
            return 'public'
    
    def _is_ip_in_networks(self, ip: ipaddress.IPv4Address, networks: Set[ipaddress.IPv4Network]) -> bool:
        """
        Check if IP is in any of the specified networks.
        
        Args:
            ip: IP address object
            networks: Set of network objects
            
        Returns:
            True if IP is in any network
        """
        return any(ip in network for network in networks)
    
    def _load_trusted_networks(self) -> Set[ipaddress.IPv4Network]:
        """
        Load trusted IP networks from configuration.
        These IPs get higher rate limits.
        
        Returns:
            Set of trusted network objects
        """
        # TODO: Load from Django settings or environment
        trusted_ips = [
            # Local development
            '127.0.0.0/8',      # Localhost
            '10.0.0.0/8',       # Private network
            '172.16.0.0/12',    # Private network
            '192.168.0.0/16',   # Private network
            
            # Add your CDN/proxy IPs here
            # '1.2.3.0/24',     # Example CDN range
        ]
        
        networks = set()
        for ip_range in trusted_ips:
            try:
                networks.add(ipaddress.ip_network(ip_range))
            except ValueError as e:
                logger.error(f"Invalid trusted IP range {ip_range}: {e}")
        
        return networks
    
    def _load_blocked_networks(self) -> Set[ipaddress.IPv4Network]:
        """
        Load blocked IP networks from configuration.
        These IPs are completely blocked.
        
        Returns:
            Set of blocked network objects
        """
        # TODO: Load from Django settings, database, or external service
        blocked_ips = [
            # Add known malicious IP ranges here
            # '192.0.2.0/24',   # Example blocked range
        ]
        
        networks = set()
        for ip_range in blocked_ips:
            try:
                networks.add(ipaddress.ip_network(ip_range))
            except ValueError as e:
                logger.error(f"Invalid blocked IP range {ip_range}: {e}")
        
        return networks
    def _get_ip_rate_limits(self, ip_category: str) -> Dict[str, Dict[str, int]]:
        """Get rate limits by action type and IP category from centralized config."""
        from ..config.limits import rate_limit_config
        
        # GET IP LIMITS (not user limits!)
        ip_limits = rate_limit_config.get_ip_rate_limits()
        return ip_limits.get(ip_category, ip_limits.get('public', {}))
    
    def get_exception_class(self):
        """Return IP-specific rate limit exception."""
        return IPRateLimitExceeded
    
    def is_allowed(self, request: HttpRequest, view: Any = None) -> tuple[bool, Dict[str, Any]]:
        """
        Check if IP request is allowed, with blocking support.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        client_ip = self._get_client_ip(request)
        if not client_ip:
            logger.warning(f"Could not determine client IP for request: {request.path}")
            return True, {'reason': 'no_ip'}
        
        # Check if IP is completely blocked
        ip_category = self._categorize_ip(client_ip)
        if ip_category == 'blocked':
            logger.warning(f"Blocked IP {client_ip} attempted access to {request.path}")
            return False, {
                'reason': 'blocked_ip',
                'ip_category': ip_category,
                'remaining': 0,
                'reset_time': 0
            }
        
        # Perform normal rate limit check
        is_allowed, metadata = super().is_allowed(request, view)
        
        # Add IP-specific metadata
        metadata.update({
            'client_ip': client_ip,
            'ip_category': ip_category,
        })
        
        return is_allowed, metadata
    
    def get_rate_limit_headers(self, request: HttpRequest, metadata: Dict[str, Any]) -> Dict[str, str]:
        """
        Get HTTP headers for IP-based rate limit information.
        
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
        
        # Add IP-specific headers (be careful about privacy)
        if 'ip_category' in metadata:
            headers['X-RateLimit-IP-Category'] = metadata['ip_category']
        
        headers['X-RateLimit-Action-Type'] = self.action_type
        
        return headers
    
    def __str__(self):
        """String representation of IP rate limiter."""
        return f"IPRateLimiter(action={self.action_type}, algorithm={self.algorithm})"