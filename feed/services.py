from django.db import DatabaseError
from django.db.models import Prefetch
from follows.services import get_following
from posts.services import get_user_posts_by_id, post_view_eligibility
from posts.models import Post, Like, Comment
import logging

logger = logging.getLogger(__name__)

def get_user_interests(user):
    try:
        interests = user.interests.values_list('name', flat=True)
        return list(interests) if interests else []
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching interests: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching interests: {str(e)}")

def get_interest_based_posts(user):
    try:
        interest_tags = get_user_interests(user)
        if not interest_tags:
            return []
        followed_user_ids = set(get_following(user.id).values_list('id', flat=True))
        posts = Post.objects.filter(
            privacy='public',
            tags__name__in=interest_tags
        ).exclude(user_id__in=followed_user_ids).prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).order_by('-created_at')
        eligible_posts = [post for post in posts if post_view_eligibility(user, post)]
        return eligible_posts
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching interest-based posts: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching interest-based posts: {str(e)}")

def get_interaction_based_posts(user):
    try:
        liked_posts = Post.objects.filter(likes__user=user).values_list('user_id', flat=True)
        saved_posts = Post.objects.filter(saves__user=user).values_list('user_id', flat=True)
        interacted_user_ids = set(liked_posts).union(saved_posts)
        followed_user_ids = set(get_following(user.id).values_list('id', flat=True))
        potential_user_ids = interacted_user_ids - followed_user_ids - {user.id}
        if not potential_user_ids:
            return []
        posts = Post.objects.filter(
            user_id__in=potential_user_ids,
            privacy='public'
        ).prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).order_by('-created_at')
        eligible_posts = [post for post in posts if post_view_eligibility(user, post)]
        return eligible_posts
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching interaction-based post: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching interaction-based post: {str(e)}")

def get_user_feed(user, page=1):
    try:
        # 1. Get all eligible posts from followed users
        followed_user_ids = set(get_following(user.id).values_list('id', flat=True))
        all_followed_posts = []
        for user_id in followed_user_ids:
            posts = get_user_posts_by_id(user_id)
            for post in posts:
                if post_view_eligibility(user, post):
                    all_followed_posts.append(post)
        all_followed_posts = sorted(all_followed_posts, key=lambda x: x.created_at, reverse=True)

        # 2. Get all interaction-based posts
        interaction_posts = get_interaction_based_posts(user)

        # 3. Get all interest-based posts
        interest_posts = get_interest_based_posts(user)

        # 4. Get all remaining followed posts (after first 5)
        remaining_followed_posts = all_followed_posts[5:]

        # --- Per-page batching ---
        page_size = 10  # 5+1+2+2
        idx = page - 1

        # Slice each category for this page
        followed_batch = all_followed_posts[idx*5:(idx+1)*5]
        interaction_batch = interaction_posts[idx:idx+1]
        interest_batch = interest_posts[idx*2:(idx+1)*2]
        remaining_batch = remaining_followed_posts[idx*2:(idx+1)*2]

        # Annotate with source
        batched = (
            [(p, "followed") for p in followed_batch] +
            [(p, "interaction") for p in interaction_batch] +
            [(p, "interest") for p in interest_batch] +
            [(p, "followed_remaining") for p in remaining_batch]
        )

        # Deduplicate by post.id, keep order
        seen = set()
        unique_posts = []
        for post, source in sorted(batched, key=lambda x: x[0].created_at, reverse=True):
            if post and post.id not in seen:
                unique_posts.append({"post": post, "source": source})
                seen.add(post.id)

        return unique_posts

    except DatabaseError as e:
        raise DatabaseError(f"Database error while generating feed: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while generating feed: {str(e)}")