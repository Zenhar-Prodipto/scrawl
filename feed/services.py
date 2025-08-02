import json
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.db import DatabaseError
from django.db.models import Prefetch, Q, Count
from django.core.cache import cache
from follows.services import FollowService
from posts.services import PostService
from posts.models import Post, Like, Comment, Save
from users.models import User
from datetime import datetime, timedelta
from django.utils import timezone  
from scrawl.core.caching import cache_manager, invalidate
from scrawl.core.monitoring.metrics.collectors import record_feed_request, record_feed_operation,record_feed_generation_time
import time

logger = logging.getLogger(__name__)


# Config
FEED_PAGE_SIZE = 10
CACHE_TIMEOUT = 3600  # 1 hour
MAX_FEED_SIZE = 1000  # Limit total feed size

class FeedService:
    @staticmethod
    def _get_user_following_cached(user_id: int) -> set:
        cached = cache_manager.get('user_following', user_id=user_id)
        if cached:
            return set(cached)
        
        following = FollowService.get_following(user_id) # Returns list of User objects
        following_ids = set(user.id for user in following) # Extract IDs manually
        cache_manager.set('user_following', list(following_ids), user_id=user_id)
        return following_ids

    @staticmethod
    def _get_user_interactions(user: User) -> Dict[str, set]:
        liked_user_ids = set(Post.objects.filter(likes__user=user).values_list('user_id', flat=True).distinct())
        saved_user_ids = set(Post.objects.filter(saves__user=user).values_list('user_id', flat=True).distinct())
        commented_user_ids = set(Post.objects.filter(comments__user=user).values_list('user_id', flat=True).distinct())
        return {
            'all': liked_user_ids.union(saved_user_ids).union(commented_user_ids)
        }

    @staticmethod
    def _build_optimized_feed(user: User) -> List[Dict[str, Any]]:
        following_ids = FeedService._get_user_following_cached(user.id)
        interaction_data = FeedService._get_user_interactions(user)
        user_interests = list(user.interests.values_list('name', flat=True))

        # Base queryset with all annotations and prefetches, no slice yet
        base_queryset = Post.objects.select_related('user').prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user').order_by('-created_at')),
            Prefetch('saves', queryset=Save.objects.select_related('user'))
        ).annotate(
            likes_count=Count('likes', distinct=True),
            comments_count=Count('comments', distinct=True),
            saves_count=Count('saves', distinct=True)
        )

        feed_posts = []

        # 1. Followed users (30 days)
        if following_ids:
            followed_posts = base_queryset.filter(
                user_id__in=following_ids,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).order_by('-created_at')
            followed_posts = followed_posts[:200]  #  slice after filtering
            for post in followed_posts:
                if FeedService._is_post_visible(user, post):
                    feed_posts.append({
                        'post': post,
                        'source': 'following',
                        'score': FeedService._calculate_post_score(post, 'following')
                    })

        # 2. Interactions (14 days)
        interaction_user_ids = interaction_data['all'] - following_ids - {user.id}
        if interaction_user_ids:
            interaction_posts = base_queryset.filter(
                user_id__in=interaction_user_ids,
                privacy='public',
                created_at__gte=timezone.now() - timedelta(days=14)
            ).order_by('-created_at')
            interaction_posts = interaction_posts[:100]  # slice after filtering
            for post in interaction_posts:
                if FeedService._is_post_visible(user, post):
                    feed_posts.append({
                        'post': post,
                        'source': 'interaction',
                        'score': FeedService._calculate_post_score(post, 'interaction')
                    })

        # 3. Interests (7 days)
        if user_interests:
            interest_posts = base_queryset.filter(
                Q(tags__name__in=user_interests) | Q(text__icontains=' '.join(user_interests[:3])),
                privacy='public',
                created_at__gte=timezone.now() - timedelta(days=7)
            ).exclude(user_id__in=following_ids.union(interaction_user_ids).union({user.id}))\
            .distinct().order_by('-created_at')
            interest_posts = interest_posts[:50]  # slice after filtering
            for post in interest_posts:
                if FeedService._is_post_visible(user, post):
                    feed_posts.append({
                        'post': post,
                        'source': 'interest',
                        'score': FeedService._calculate_post_score(post, 'interest')
                    })
        if len(feed_posts) < 5:  #threshold for fallback
            print(f"Feed too small for user {user.id} ({len(feed_posts)} posts), adding fallback")
            logger.info(f"Feed too small for user {user.id} ({len(feed_posts)} posts), adding fallback")
            existing_post_ids = {item['post'].id for item in feed_posts}
            fallback_posts = FeedService._build_fallback_feed(user, existing_post_ids)
            feed_posts.extend(fallback_posts)

        # 4. Deduplicate and sort
        seen_posts = set()
        unique_posts = []
        for item in feed_posts:
            if item['post'].id not in seen_posts:
                unique_posts.append(item)
                seen_posts.add(item['post'].id)
        unique_posts.sort(key=lambda x: (x['score'], x['post'].created_at), reverse=True)
        return unique_posts[:MAX_FEED_SIZE]

    @staticmethod
    def _calculate_post_score(post: Post, source: str) -> float:
        base_scores = {'following': 100, 'interaction': 50, 'interest': 25,'older_following': 20,'trending': 15}
        score = base_scores.get(source, 10)
        score += (post.likes_count * 2 + post.comments_count * 3 + post.saves_count * 5)
        age_hours = (timezone.now() - post.created_at).total_seconds() / 3600
        decay_factor = max(0.1, 1 - (age_hours / 168))  # Decay over a week
        return score * decay_factor
    
    @staticmethod
    def _build_fallback_feed(user: User, existing_post_ids: set) -> List[Dict[str, Any]]:
        """
        Fallback feed when main feed has < 5 posts.
        Priority: 1) Older posts from following, 2) Trending public posts
        """
        try:
            following_ids = FeedService._get_user_following_cached(user.id)
            fallback_posts = []
            
            base_queryset = Post.objects.select_related('user').prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user').order_by('-created_at')),
                Prefetch('saves', queryset=Save.objects.select_related('user'))
            ).annotate(
                likes_count=Count('likes', distinct=True),
                comments_count=Count('comments', distinct=True),
                saves_count=Count('saves', distinct=True)
            )

            # 1. OLDER POSTS FROM FOLLOWING (6 months back)
            if following_ids:
                older_followed_posts = base_queryset.filter(
                    user_id__in=following_ids,
                    created_at__gte=timezone.now() - timedelta(days=180)  # 6 months
                ).exclude(
                    id__in=existing_post_ids  # Don't duplicate existing posts
                ).order_by('-created_at')[:15]
                
                for post in older_followed_posts:
                    if FeedService._is_post_visible(user, post):
                        fallback_posts.append({
                            'post': post,
                            'source': 'older_following',
                            'score': FeedService._calculate_post_score(post, 'older_following')
                        })

            # 2. TRENDING PUBLIC POSTS (if still need more)
            if len(fallback_posts) < 10:  # Need more posts
                trending_posts = base_queryset.filter(
                    privacy='public',
                    created_at__gte=timezone.now() - timedelta(days=30)  # Last 30 days
                ).exclude(
                    user_id=user.id  # Don't show user's own posts
                ).exclude(
                    id__in=existing_post_ids.union({p['post'].id for p in fallback_posts})
                ).order_by('-likes_count', '-comments_count', '-created_at')[:15]
                
                for post in trending_posts:
                    if FeedService._is_post_visible(user, post):
                        fallback_posts.append({
                            'post': post,
                            'source': 'trending',
                            'score': FeedService._calculate_post_score(post, 'trending')
                        })

            return fallback_posts[:20]  # Limit fallback posts
            
        except Exception as e:
            logger.error(f"Error generating fallback feed for user {user.id}: {e}")
            return []

    @staticmethod
    def _is_post_visible(user: User, post: Post) -> bool:
        try:
            return PostService.post_view_eligibility(user, post)
        except (User.DoesNotExist, DatabaseError, Exception):
            logger.warning(f"Visibility check failed for user {user.id} and post {post.id}")
            return False

    @staticmethod
    def get_user_feed(user: User, page: int = 1) -> Dict[str, Any]:
        try:
            start_time = time.time()
            cached_page = cache_manager.get('feed_page', user_id=user.id, page=page)
            cached_meta = cache_manager.get('user_feed', user_id=user.id)  # For metadata
            
            if cached_page and cached_meta:
                record_feed_request('free', True) 
                record_feed_operation('cache_hit', True, 'free')
                duration = time.time() - start_time
                record_feed_generation_time(duration, 'free', True)

                page_data = cached_page      
                meta_data = cached_meta      
                post_ids = [item['post_id'] for item in page_data]
                posts = Post.objects.filter(id__in=post_ids).select_related('user').prefetch_related(
                    'post_images', 'tags', 'likes', 'comments', 'saves'
                )
                posts_dict = {p.id: p for p in posts}
                ordered_posts = [{'post': posts_dict[item['post_id']], 'source': item['source']} for item in page_data if item['post_id'] in posts_dict]
                return {
                    'posts': ordered_posts,
                    'has_more': page < meta_data['total_pages'],
                    'page': page,
                    'total_pages': meta_data['total_pages'],
                    'cache_hit': True
                }
            
            record_feed_request('free', False) 
            record_feed_operation('cache_miss', True, 'free')

            logger.info(f"Generating fresh feed for user {user.id}")
            feed_posts = FeedService._build_optimized_feed(user)
            total_posts = len(feed_posts)
            total_pages = (total_posts + FEED_PAGE_SIZE - 1) // FEED_PAGE_SIZE

            # Cache metadata
            meta_data = {'total_posts': total_posts, 'total_pages': total_pages, 'generated_at': datetime.now().isoformat()}
            cache_manager.set('user_feed', meta_data, user_id=user.id)  

            # Cache pages
            for p in range(1, total_pages + 1):
                start_idx = (p - 1) * FEED_PAGE_SIZE
                end_idx = start_idx + FEED_PAGE_SIZE
                page_posts = feed_posts[start_idx:end_idx]
                page_data = [{'post_id': item['post'].id, 'source': item['source']} for item in page_posts]
                cache_manager.set('feed_page', page_data, user_id=user.id, page=p) 

            # Return requested page
            start_idx = (page - 1) * FEED_PAGE_SIZE
            end_idx = start_idx + FEED_PAGE_SIZE
            page_posts = feed_posts[start_idx:end_idx]
            
            duration = time.time() - start_time
            record_feed_generation_time(duration, 'free', False)

            return {
                'posts': page_posts,
                'has_more': page < total_pages,
                'page': page,
                'total_pages': total_pages,
                'cache_hit': False
            }
        except DatabaseError as e:
            logger.error(f"Database error generating feed for user {user.id}: {e}")
            raise DatabaseError(f"Database error while generating feed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error generating feed for user {user.id}: {e}")
            raise Exception(f"Unexpected error while generating feed: {str(e)}")
    @staticmethod
    def invalidate_user_feed(user_id: int):
        invalidate.invalidate_feed_cache(user_id)
        logger.info(f"Invalidated feed cache for user {user_id}")

    @staticmethod
    def invalidate_follower_feeds(user_id: int):
        from follows.models import Follow
        follower_ids = Follow.objects.filter(followed_id=user_id).values_list('follower_id', flat=True)
        for follower_id in follower_ids:
            FeedService.invalidate_user_feed(follower_id)
        logger.info(f"Invalidated feeds for {len(follower_ids)} followers of user {user_id}")

# Backward compatibility
get_user_feed = FeedService.get_user_feed
invalidate_user_feed = FeedService.invalidate_user_feed
invalidate_follower_feeds = FeedService.invalidate_follower_feeds