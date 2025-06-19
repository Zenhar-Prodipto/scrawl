# feed/services.py
from django.db import DatabaseError
from django.db.models import Prefetch
from follows.services import get_following, check_follow_status, check_super_follower
from posts.services import get_user_posts_by_id, post_view_eligibility, get_post_by_id
from posts.models import Post, Like, Save, Tag, Comment
from users.models import User, Interest
from users.services import get_user_by_id
import logging
logger = logging.getLogger(__name__)

def get_user_interests(user):
    """
    Fetch the user's interests based on signup data.
    Args:
        user (User): The authenticated user.
    Returns:
        list: List of interest names.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        interests = user.interests.values_list('name', flat=True)
        return list(interests) if interests else []
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching interests: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching interests: {str(e)}")
    

def get_interest_based_posts(user, limit=2):
    try:
        interest_tags = get_user_interests(user)
        print(f"User interests: {interest_tags}")
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
        ).order_by('-created_at')[:limit * 2]

        eligible_posts = [post for post in posts if post_view_eligibility(user, post)]
        print(f"Interest-based posts found: {[p.id for p in eligible_posts]}")
        return eligible_posts[:limit]
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching interest-based posts: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching interest-based posts: {str(e)}")
    
def get_interaction_based_post(user):
    try:
        liked_posts = Post.objects.filter(likes__user=user).values_list('user_id', flat=True)
        saved_posts = Post.objects.filter(saves__user=user).values_list('user_id', flat=True)
        interacted_user_ids = set(liked_posts).union(saved_posts)

        followed_user_ids = set(get_following(user.id).values_list('id', flat=True))
        potential_user_ids = interacted_user_ids - followed_user_ids - {user.id}

        print(f"Interaction potential user IDs: {potential_user_ids}")
        if not potential_user_ids:
            return None

        posts = Post.objects.filter(
            user_id__in=potential_user_ids,
            privacy='public'
        ).prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).order_by('-created_at')

        for post in posts:
            if post_view_eligibility(user, post):
                return post
        return None
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching interaction-based post: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching interaction-based post: {str(e)}")
    
def get_user_feed(user):
    try:
       
        followed_user_ids = set(get_following(user.id).values_list('id', flat=True))
        followd = get_following(user.id)
        # 1. Get 5 newest posts from followed users
        all_followed_posts = []
        for user_id in followed_user_ids:
            posts = get_user_posts_by_id(user_id)
            print(f"Checking posts for user {user_id}")
            for post in posts:
                is_eligible = post_view_eligibility(user, post)
                if is_eligible:
                    all_followed_posts.append(post)
                    print(f"Eligible post {post.id} from user {user_id} (privacy: {post.privacy}, profile_type: {post.user.profile_type})")
                else:
                    print(f"Ineligible post {post.id} from user {user_id} (reason: not eligible)")
        all_followed_posts = sorted(all_followed_posts, key=lambda x: x.created_at, reverse=True)
        followed_posts = all_followed_posts[:5]
        followed_posts = [(post, "followed") for post in followed_posts]

        # 2. Get 1 interaction-based post
        interaction_post = get_interaction_based_post(user)
        interaction_posts = [(interaction_post, "interaction")] if interaction_post else []

        # 3. Get 2 interest-based posts
        interest_posts = get_interest_based_posts(user, limit=2)
        interest_posts = [(post, "interest") for post in interest_posts]

        # 4. Get 2 more followed posts (next newest after the first 5)
        remaining_followed_posts = []
        if len(followed_posts) >= 5:
            earliest_five = min([p[0] for p in followed_posts], key=lambda x: x.created_at).created_at
            for user_id in followed_user_ids:
                posts = get_user_posts_by_id(user_id).filter(created_at__lt=earliest_five)
                for post in posts:
                    is_eligible = post_view_eligibility(user, post)
                    if is_eligible:
                        remaining_followed_posts.append(post)
                        print(f"Eligible remaining post {post.id} from user {user_id}")
                    else:
                        print(f"Ineligible remaining post {post.id} from user {user_id}")
                    if len(remaining_followed_posts) >= 2:
                        break
                if len(remaining_followed_posts) >= 2:
                    break
            remaining_followed_posts = sorted(remaining_followed_posts, key=lambda x: x.created_at, reverse=True)[:2]
        remaining_followed_posts = [(post, "followed_remaining") for post in remaining_followed_posts]

        # Combine all posts, removing duplicates by post.id
        all_posts = followed_posts + interaction_posts + interest_posts + remaining_followed_posts
        seen = set()
        unique_posts = []
        for post, source in all_posts:
            if post and post.id not in seen:
                unique_posts.append({"post": post, "source": source})
                seen.add(post.id)

        return unique_posts
    except DatabaseError as e:
        raise DatabaseError(f"Database error while generating feed: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while generating feed: {str(e)}")