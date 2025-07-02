import redis
import json
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.db import DatabaseError
from django.db.models import Prefetch, Q, Count
from django.core.cache import cache
from follows.services import FollowService
from posts.services import post_view_eligibility
from posts.models import Post, Like, Comment, Save
from users.models import User
from datetime import datetime, timedelta
from django.utils import timezone  # Add this for timezone handling

logger = logging.getLogger(__name__)

# Redis client
redis_client = redis.Redis.from_url(settings.REDIS_URL)

# Cache keys
FEED_CACHE_KEY = "feed:{user_id}:page:{page}"
FEED_META_KEY = "feed_meta:{user_id}"
USER_FOLLOWING_KEY = "following:{user_id}"

# Config
FEED_PAGE_SIZE = 10
CACHE_TIMEOUT = 3600  # 1 hour
MAX_FEED_SIZE = 1000  # Limit total feed size

class FeedService:
    @staticmethod
    def _get_user_following_cached(user_id: int) -> set:
        cache_key = USER_FOLLOWING_KEY.format(user_id=user_id)
        cached = redis_client.get(cache_key)
        if cached:
            return set(json.loads(cached))
        following_ids = set(FollowService.get_following(user_id).values_list('id', flat=True))
        redis_client.setex(cache_key, CACHE_TIMEOUT, json.dumps(list(following_ids)))
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
            followed_posts = followed_posts[:200]  # Apply slice after filtering
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
            interaction_posts = interaction_posts[:100]  # Apply slice after filtering
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
            interest_posts = interest_posts[:50]  # Apply slice after filtering
            for post in interest_posts:
                if FeedService._is_post_visible(user, post):
                    feed_posts.append({
                        'post': post,
                        'source': 'interest',
                        'score': FeedService._calculate_post_score(post, 'interest')
                    })

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
        base_scores = {'following': 100, 'interaction': 50, 'interest': 25}
        score = base_scores.get(source, 10)
        score += (post.likes_count * 2 + post.comments_count * 3 + post.saves_count * 5)
        age_hours = (timezone.now() - post.created_at).total_seconds() / 3600
        decay_factor = max(0.1, 1 - (age_hours / 168))  # Decay over a week
        return score * decay_factor

    @staticmethod
    def _is_post_visible(user: User, post: Post) -> bool:
        try:
            return post_view_eligibility(user, post)
        except (User.DoesNotExist, DatabaseError, Exception):
            logger.warning(f"Visibility check failed for user {user.id} and post {post.id}")
            return False

    @staticmethod
    def get_user_feed(user: User, page: int = 1) -> Dict[str, Any]:
        try:
            cache_key = FEED_CACHE_KEY.format(user_id=user.id, page=page)
            meta_key = FEED_META_KEY.format(user_id=user.id)

            cached_page = redis_client.get(cache_key)
            cached_meta = redis_client.get(meta_key)

            if cached_page and cached_meta:
                page_data = json.loads(cached_page)
                meta_data = json.loads(cached_meta)
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

            logger.info(f"Generating fresh feed for user {user.id}")
            feed_posts = FeedService._build_optimized_feed(user)
            total_posts = len(feed_posts)
            total_pages = (total_posts + FEED_PAGE_SIZE - 1) // FEED_PAGE_SIZE

            # Cache metadata
            meta_data = {'total_posts': total_posts, 'total_pages': total_pages, 'generated_at': datetime.now().isoformat()}
            redis_client.setex(meta_key, CACHE_TIMEOUT, json.dumps(meta_data))

            # Cache pages
            for p in range(1, total_pages + 1):
                start_idx = (p - 1) * FEED_PAGE_SIZE
                end_idx = start_idx + FEED_PAGE_SIZE
                page_posts = feed_posts[start_idx:end_idx]
                page_data = [{'post_id': item['post'].id, 'source': item['source']} for item in page_posts]
                page_cache_key = FEED_CACHE_KEY.format(user_id=user.id, page=p)
                redis_client.setex(page_cache_key, CACHE_TIMEOUT, json.dumps(page_data))

            # Return requested page
            start_idx = (page - 1) * FEED_PAGE_SIZE
            end_idx = start_idx + FEED_PAGE_SIZE
            page_posts = feed_posts[start_idx:end_idx]

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
        pattern = f"feed:{user_id}:*"
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
        following_key = USER_FOLLOWING_KEY.format(user_id=user_id)
        redis_client.delete(following_key)
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