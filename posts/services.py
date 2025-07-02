from datetime import datetime
from django.db import DatabaseError, transaction
from django.db.models import Prefetch
from follows.services import check_follow_status, check_super_follower
from users.models import User
from users.services import get_user_by_id
from .models import Post, PostImage, Tag, Like, Comment, Save
from scrawl.config.kafka_config import producer, delivery_report
import json
import redis
from django.conf import settings

# Redis client
redis_client = redis.Redis.from_url(settings.REDIS_URL)

# Cache keys
POST_CACHE_KEY = "post:{post_id}"
USER_POSTS_CACHE_KEY = "user_posts:{user_id}"
SAVED_POSTS_CACHE_KEY = "saved_posts:{user_id}"
LIKE_EXISTS_CACHE_KEY = "like_exists:{user_id}:{post_id}"
COMMENT_EXISTS_CACHE_KEY = "comment_exists:{user_id}:{post_id}"

def create_post(user, validated_data, tags_data):
    """
    Create a new post with associated images and tags. 
    Args:
        user (User): The authenticated user creating the post.
        validated_data (dict): Validated data containing text, privacy, and post_images.
        tags_data (list): List of tag names.
    Returns:
        Post: The created post instance.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        post_images_data = validated_data.pop('post_images', [])

        with transaction.atomic():
            post = Post.objects.create(user=user, **validated_data)

            for tag_name in tags_data:
                tag, _ = Tag.objects.get_or_create(name=tag_name.strip())
                post.tags.add(tag)

            for image_data in post_images_data:
                PostImage.objects.create(post=post, **image_data)

            # Publish post event
            event = {
                "event_type": "post.created",
                "post_id": post.id,
                "user_id": user.id,
                "created_at": post.created_at.isoformat(),
                "privacy": post.privacy
            }
            producer.produce(
                "post.events",
                value=json.dumps(event).encode('utf-8'),
                callback=delivery_report
            )
            producer.flush()  # Ensure delivery (remove in prod)

            # Invalidate caches
            redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
            redis_client.delete(USER_POSTS_CACHE_KEY.format(user_id=user.id))
            print("Cache invalidated for post and user posts:", post.id, user.id,flush=True)

            return post
    except DatabaseError as e:
        raise DatabaseError(f"Database error during post creation: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error during post creation: {str(e)}")
    
def get_self_post_by_id(post_id, user):
    """
    Fetch a post by ID, ensuring it belongs to the authenticated user.
    Args:
        post_id (int): The ID of the post.
        user (User): The authenticated user.
    Returns:
        Post: The post instance.
    Raises:
        Post.DoesNotExist: If the post doesn't exist or doesn't belong to the user.
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        # Prefetch related data to optimize queries
        post = Post.objects.prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).get(id=post_id, user=user)
        return post
    except Post.DoesNotExist:
        raise Post.DoesNotExist("Post not found or you don't have access to it.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching post: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching post: {str(e)}")

def get_post_by_id(post_id: int) -> Post:
    """
    Fetch a post by ID, including related data.
    Args:
        post_id (int): The ID of the post.
    Returns:
        Post: The post instance with related data.
    Raises:
        Post.DoesNotExist: If the post doesn't exist.
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        cache_key = POST_CACHE_KEY.format(post_id=post_id)
        cached_post = redis_client.get(cache_key)
        if cached_post:
            print("Cache hit for post:", post_id,flush=True)
            return Post.objects.prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).get(id=post_id)
        post = Post.objects.prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).get(id=post_id)
        redis_client.setex(cache_key, 300, post.id)  # 5m TTL
        print("Cache miss for post:", post_id,flush=True)
        return post
    except Post.DoesNotExist:
        raise Post.DoesNotExist("Post not found.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching post: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching post: {str(e)}")
    
def get_user_posts(user):
    """
    Fetch all posts for the authenticated user, optimized for listing.
    Args:
        user (User): The authenticated user.
    Returns:
        QuerySet: A queryset of the user's posts.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        cache_key = USER_POSTS_CACHE_KEY.format(user_id=user.id)
        cached_posts = redis_client.get(cache_key)
        if cached_posts:
            print("Cache hit for user posts:", user.id,flush=True)
            post_ids = json.loads(cached_posts)
            return Post.objects.prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).filter(id__in=post_ids).order_by('-created_at')
        posts = Post.objects.filter(user=user).prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).order_by('-created_at')
        redis_client.setex(cache_key, 300, json.dumps([p.id for p in posts]))  # 5m TTL
        print("Cache miss for user posts:", user.id,flush=True)
        return posts
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching posts: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching posts: {str(e)}")
    

def update_post(post, user, validated_data):
    """
    Update a post's text, privacy, tags, and images.
    """
    try:
        with transaction.atomic():
            if 'text' in validated_data:
                post.text = validated_data['text']
            if 'privacy' in validated_data:
                post.privacy = validated_data['privacy']

            tags_to_add = validated_data.get('tags_to_add', [])
            tags_to_remove = validated_data.get('tags_to_remove', [])

            for tag_name in tags_to_add:
                tag, _ = Tag.objects.get_or_create(name=tag_name.strip())
                post.tags.add(tag)

            for tag_name in tags_to_remove:
                try:
                    tag = Tag.objects.get(name=tag_name.strip())
                    post.tags.remove(tag)
                except Tag.DoesNotExist:
                    pass

            images_to_add = validated_data.get('post_images_to_add', [])
            images_to_remove = validated_data.get('post_images_to_remove', [])

            if images_to_remove:
                PostImage.objects.filter(id__in=images_to_remove, post=post).delete()

            for image_data in images_to_add:
                PostImage.objects.create(post=post, **image_data)

            post.save()

            # Publish update event
            event = {
                "event_type": "post.updated",
                "post_id": post.id,
                "user_id": user.id,
                "created_at": post.updated_at.isoformat() if hasattr(post, 'updated_at') else post.created_at.isoformat(),
                "privacy": post.privacy
            }
            producer.produce(
                "post.events",
                value=json.dumps(event).encode('utf-8'),
                callback=delivery_report
            )
            producer.flush()  # Ensure delivery (remove in prod)

            # Invalidate caches
            redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
            redis_client.delete(USER_POSTS_CACHE_KEY.format(user_id=user.id))
            print("Cache invalidated for post and user posts:", post.id, user.id,flush=True)

            return post
    except DatabaseError as e:
        raise DatabaseError(f"Database error during post update: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error during post update: {str(e)}")
    
    
def delete_post(post, user):
    """
    Delete a post.
    """
    try:
        with transaction.atomic():
            if post.user != user:
                raise Post.DoesNotExist("You do not have permission to delete this post.")
            post_id = post.id
            post.delete()

            # Publish delete event
            event = {
                "event_type": "post.deleted",
                "post_id": post_id,
                "user_id": user.id,
                "created_at": datetime.now().isoformat()
            }
            producer.produce(
                "post.events",
                value=json.dumps(event).encode('utf-8'),
                callback=delivery_report
            )
            producer.flush()  # Ensure delivery (remove in prod)

            # Invalidate caches
            redis_client.delete(POST_CACHE_KEY.format(post_id=post_id))
            redis_client.delete(USER_POSTS_CACHE_KEY.format(user_id=user.id))
            print("Cache invalidated for post and user posts:", post_id, user.id,flush=True)
    except DatabaseError as e:
        raise DatabaseError(f"Database error during post deletion: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error during post deletion: {str(e)}")
    
def check_like_eligibility(requesting_user, post):
    """
    Check if the requesting user is eligible to like a post based on visibility rules.
    Args:
        requesting_user (User): The user attempting to like the post.
        post (Post): The post to be liked.
    Returns:
        bool: True if eligible, False otherwise.
    Raises:
        User.DoesNotExist: If the post's user doesn't exist.
        DatabaseError: If a database error occurs.
    """
    try:
        target_user = post.user
        
        # Check if the user has already liked the post
        if Like.objects.filter(user=requesting_user, post=post).exists():
            return False  # Already liked, not eligible to like again
        
        # Check if the target user exists and is not deleted
        target_user_exists= get_user_by_id(target_user.id)
        if not target_user_exists:
            raise User.DoesNotExist("Target user does not exist or has been deleted.")
        
        # Allow Liking on own posts
        if requesting_user == target_user:
            return True

        # Check follow status and super follower status
        is_following = check_follow_status(requesting_user, target_user.id)
        is_super_follower = check_super_follower(requesting_user, target_user)
        
        # Public profile rules
        if target_user.profile_type =='public':
            if post.privacy == 'public':
                print(f"public post rules: {post.privacy}", flush=True)
                return True  # Anyone can like public posts on a public profile
            elif post.privacy == 'private':
                print(f"private post rules: {post.privacy}", flush=True)
                return is_super_follower  # Only super followers can like private posts
        
        # Private profile rules
        else:
            if not is_following:
                return False  # Non-followers can't like anything on a private profile
            if post.privacy == 'public':
                return True  # Followers can like public posts on a private profile
            elif post.privacy == 'private':
                return is_super_follower  # Only super followers can like private posts
        
        return False  # Fallback (shouldn't reach here)

    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while checking eligibility: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while checking eligibility: {str(e)}")
    
def create_like(requesting_user, post):
    """
    Create a new like for a post by the requesting user.
    Args:
        requesting_user (User): The user liking the post.
        post (Post): The post to like.
    Returns:
        Like: The created like instance.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        with transaction.atomic():
            like = Like.objects.create(user=requesting_user, post=post)
            
            # Publish like event
            event = {
                "event_type": "like.created",
                "user_id": requesting_user.id,
                "post_id": post.id,
                "created_at": like.created_at.isoformat()
            }
            producer.produce(
                "like.events",
                value=json.dumps(event).encode('utf-8'),
                callback=delivery_report
            )
            producer.flush()  # Ensure delivery (remove in prod)

            # Invalidate caches
            redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
            redis_client.delete(LIKE_EXISTS_CACHE_KEY.format(user_id=requesting_user.id, post_id=post.id))
            print("Cache invalidated for post and like status:", post.id, requesting_user.id,flush= True)

            return like
    except DatabaseError as e:
        raise DatabaseError(f"Database error while creating like: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while creating like: {str(e)}")
    
def delete_like(requesting_user, post):
    """
    Delete a like for a post by the requesting user.
    Args:
        requesting_user (User): The user unliking the post.
        post (Post): The post to unlike.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        with transaction.atomic():
            like = Like.objects.filter(user=requesting_user, post=post).first()
            if like:
                like.delete()

                # Invalidate caches
                redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
                redis_client.delete(LIKE_EXISTS_CACHE_KEY.format(user_id=requesting_user.id, post_id=post.id))
                print("Cache invalidated for post and like status:", post.id, requesting_user.id,flush= True)
    except DatabaseError as e:
        raise DatabaseError(f"Database error while deleting like: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while deleting like: {str(e)}")
    
    
def check_if_like_exists(requesting_user, post):
    """
    Check if a like exists for a post by the requesting user.
    Args:
        requesting_user (User): The user checking the like.
        post (Post): The post to check.
    Returns:
        bool: True if the like exists, False otherwise.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        cache_key = LIKE_EXISTS_CACHE_KEY.format(user_id=requesting_user.id, post_id=post.id)
        cached_status = redis_client.get(cache_key)
        if cached_status is not None:
            print("Cache hit for like existence:", requesting_user.id, post.id)
            return json.loads(cached_status)
        status = Like.objects.filter(user=requesting_user, post=post).exists()
        redis_client.setex(cache_key, 60, json.dumps(status))  # 1m TTL
        print("Cache miss for like existence:", requesting_user.id, post.id,flush=True)
        return status
    except DatabaseError as e:
        raise DatabaseError(f"Database error while checking like existence: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while checking like existence: {str(e)}")
    
def check_comment_eligibility(requesting_user, post):
    """
    Check if the requesting user is eligible to comment on a post based on visibility rules.
    Args:
        requesting_user (User): The user attempting to comment.
        post (Post): The post to comment on.
    Returns:
        bool: True if eligible, False otherwise.
    Raises:
        User.DoesNotExist: If the post's user doesn't exist.
        DatabaseError: If a database error occurs.
    """
    try:
        target_user = post.user
        
        # Check if the target user exists and is not deleted
        target_user_exists = get_user_by_id(target_user.id)
        if not target_user_exists:
            raise User.DoesNotExist("Target user does not exist or has been deleted.")

        # Check follow status and super follower status
        is_following = check_follow_status(requesting_user, target_user.id)
        is_super_follower = check_super_follower(requesting_user, target_user)
        
        # Allow commenting on own posts
        if requesting_user == target_user:
            return True

        # Public profile rules
        if target_user.profile_type == 'public':
            if post.privacy == 'public':
                return True  # Anyone can comment on public posts on a public profile
            elif post.privacy == 'private':
                return is_super_follower  # Only super followers can comment on private posts
        
        # Private profile rules
        else:
            if not is_following:
                return False  # Non-followers can't comment on a private profile
            if post.privacy == 'public':
                return True  # Followers can comment on public posts on a private profile
            elif post.privacy == 'private':
                return is_super_follower  # Only super followers can comment on private posts
        
        return False  # Fallback (shouldn't reach here)

    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while checking eligibility: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while checking eligibility: {str(e)}")

def create_comment(requesting_user, post, text):
    """
    Create a new comment for a post by the requesting user.
    Args:
        requesting_user (User): The user commenting on the post.
        post (Post): The post to comment on.
        text (str): The text content of the comment.
    Returns:
        Comment: The created comment instance.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        with transaction.atomic():
            comment = Comment.objects.create(user=requesting_user, post=post, text=text)

            # Invalidate caches
            redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
            redis_client.delete(COMMENT_EXISTS_CACHE_KEY.format(user_id=requesting_user.id, post_id=post.id))
            print("Cache invalidated for post and comment status:", post.id, requesting_user.id,flush=True)

            return comment
    except DatabaseError as e:
        raise DatabaseError(f"Database error while creating comment: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while creating comment: {str(e)}")
    
def check_if_comment_exists(requesting_user, post):
    """
    Check if a comment exists for a post by the requesting user.
    Args:
        requesting_user (User): The user checking the like.
        post (Post): The post to check.
    Returns:
        bool: True if the comment exists, False otherwise.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        cache_key = COMMENT_EXISTS_CACHE_KEY.format(user_id=requesting_user.id, post_id=post.id)
        cached_status = redis_client.get(cache_key)
        if cached_status is not None:
            print("Cache hit for comment existence:", requesting_user.id, post.id,flush=True)
            return json.loads(cached_status)
        status = Comment.objects.filter(user=requesting_user, post=post).exists()
        redis_client.setex(cache_key, 60, json.dumps(status))  # 1m TTL
        print("Cache miss for comment existence:", requesting_user.id, post.id,flush=True)
        return status
    except DatabaseError as e:
        raise DatabaseError(f"Database error while checking Comment existence: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while checking Comment existence: {str(e)}")
    
def update_comment(comment, text):
    """
    Update the text of an existing comment.
    Args:
        comment (Comment): The comment instance to update.
        text (str): The new text content.
    Returns:
        Comment: The updated comment instance.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        with transaction.atomic():
            comment.text = text
            comment.save()
            return comment
    except DatabaseError as e:
        raise DatabaseError(f"Database error while updating comment: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while updating comment: {str(e)}")
    
def get_comment_by_id(comment_id: int, post: Post) -> Comment:
    """
    Fetch a comment by ID, including related user data.
    Args:
        comment_id (int): The ID of the comment.
        post (Post): The post to which the comment belongs.
    Returns:
        Comment: The comment instance with related user data.
    Raises:
        Comment.DoesNotExist: If the comment doesn't exist.
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        comment = Comment.objects.get(id=comment_id, post=post)
        return comment
    except Comment.DoesNotExist:
        raise Comment.DoesNotExist("Comment not found.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching comment: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching comment: {str(e)}")
    
    
def delete_comment(comment):
    """
    Delete an existing comment.
    Args:
        comment (Comment): The comment instance to delete.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        with transaction.atomic():
            post = comment.post
            comment.delete()

            # Invalidate caches
            redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
            redis_client.delete(COMMENT_EXISTS_CACHE_KEY.format(user_id=comment.user.id, post_id=post.id))
            print("Cache invalidated for post and comment status:", post.id, comment.user.id,flush=True)
    except DatabaseError as e:
        raise DatabaseError(f"Database error while deleting comment: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while deleting comment: {str(e)}")
    
def get_save_by_user_and_post(user, post):
    try:
        save = Save.objects.get(user=user, post=post)
        return save
    except Save.DoesNotExist:
        return None
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching save: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching save: {str(e)}")

def create_save(user, post):
    try:
        with transaction.atomic():
            save = Save.objects.create(user=user, post=post)

            # Invalidate caches
            redis_client.delete(SAVED_POSTS_CACHE_KEY.format(user_id=user.id))
            redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
            print("Cache invalidated for saved posts and post:", user.id, post.id,flush=True)

            return save
    except DatabaseError as e:
        raise DatabaseError(f"Database error while creating save: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while creating save: {str(e)}")

def delete_save(user, post):
    try:
        with transaction.atomic():
            save = get_save_by_user_and_post(user, post)
            if save:
                save.delete()

                # Invalidate caches
                redis_client.delete(SAVED_POSTS_CACHE_KEY.format(user_id=user.id))
                redis_client.delete(POST_CACHE_KEY.format(post_id=post.id))
                print("Cache invalidated for saved posts and post:", user.id, post.id,flush=True)
    except DatabaseError as e:
        raise DatabaseError(f"Database error while deleting save: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while deleting save: {str(e)}")
    
def check_save_eligibility(requesting_user, post):
    try:
        target_user = post.user
        
        # Check if the target user exists and is not deleted
        target_user_exists = get_user_by_id(target_user.id)
        if not target_user_exists:
            raise User.DoesNotExist("Target user does not exist or has been deleted.")

        # Check follow status and super follower status
        is_following = check_follow_status(requesting_user, target_user.id)
        is_super_follower = check_super_follower(requesting_user, target_user)
        
        # Allow saving own posts
        if requesting_user == target_user:
            return True

        # Public profile rules
        if target_user.profile_type == 'public':
            if post.privacy == 'public':
                return True  # Anyone can save public posts on a public profile
            elif post.privacy == 'private':
                return is_super_follower  # Only super followers can save private posts
        
        # Private profile rules
        else:
            if not is_following:
                return False  # Non-followers can't save anything on a private profile
            if post.privacy == 'public':
                return True  # Followers can save public posts on a private profile
            elif post.privacy == 'private':
                return is_super_follower  # Only super followers can save private posts
        
        return False  # Fallback (shouldn't reach here)

    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while checking eligibility: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while checking eligibility: {str(e)}")
    
def get_user_saved_posts(user):
    try:
        cache_key = SAVED_POSTS_CACHE_KEY.format(user_id=user.id)
        cached_posts = redis_client.get(cache_key)
        if cached_posts:
            print("Cache hit for saved posts:", user.id,flush=True)
            post_ids = json.loads(cached_posts)
            return Post.objects.prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).filter(id__in=post_ids).order_by('-created_at')
        saved_posts = Post.objects.filter(saves__user=user).prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).order_by('-created_at')
        redis_client.setex(cache_key, 300, json.dumps([p.id for p in saved_posts]))  # 5m TTL
        print("Cache miss for saved posts:", user.id,flush=True)
        return saved_posts
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching saved posts: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching saved posts: {str(e)}")
    
def get_user_posts_by_id(user_id: int) -> User:
    """
    Fetch all posts for a specified user ID, optimized for listing.
    Args:
        user_id (int): The ID of the user whose posts to fetch.
    Returns:
        QuerySet: A queryset of the user's posts.
    Raises:
        User.DoesNotExist: If the user doesn't exist.
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        user = User.objects.get(id=user_id)
        cache_key = USER_POSTS_CACHE_KEY.format(user_id=user_id)
        cached_posts = redis_client.get(cache_key)
        if cached_posts:
            print("Cache hit for user posts:", user_id,flush=True)
            post_ids = json.loads(cached_posts)
            return Post.objects.prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).filter(id__in=post_ids).order_by('-created_at')
        posts = Post.objects.filter(user=user).prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).order_by('-created_at')
        redis_client.setex(cache_key, 300, json.dumps([p.id for p in posts]))  # 5m TTL
        print("Cache miss for user posts:", user_id,flush=True)
        return posts
    except User.DoesNotExist:
        raise User.DoesNotExist("User not found.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching posts: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching posts: {str(e)}")

def post_view_eligibility(requesting_user: User, post: Post) -> bool:
    """
    Check if the requesting user is eligible to view a post based on visibility rules.
    Args:
        requesting_user (User): The user attempting to view the post.
        post (Post): The post to check.
    Returns:
        bool: True if eligible, False otherwise.
    Raises:
        User.DoesNotExist: If the post's user doesn't exist.
        DatabaseError: If a database error occurs.
    """
    try:
        target_user = post.user
        
        # Check if the target user exists and is not deleted
        target_user_exists = get_user_by_id(target_user.id)
        if not target_user_exists:
            raise User.DoesNotExist("Target user does not exist or has been deleted.")

        # Allow viewing own posts
        if requesting_user == target_user:
            return True

        # Check follow status and super follower status
        is_following = check_follow_status(requesting_user, target_user.id)
        is_super_follower = check_super_follower(requesting_user, target_user)
        # Public profile rules
        if target_user.profile_type == 'public':
            if post.privacy == 'public':
                return True  # Anyone can view public posts on a public profile
            elif post.privacy == 'private':
                return is_super_follower  # Only super followers can view private posts
        
        # Private profile rules
        else:
            if not is_following:
                return False  # Non-followers can't view anything on a private profile
            if post.privacy == 'public':
                return True  # Followers can view public posts on a private profile
            elif post.privacy == 'private':
                return is_super_follower  # Only super followers can view private posts
        
        return False  # Fallback (shouldn't reach here)

    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error while checking eligibility: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while checking eligibility: {str(e)}")