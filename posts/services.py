from django.db import DatabaseError, transaction
from django.db.models import Prefetch

from follows.services import check_follow_status, check_super_follower
from users.models import User
from users.services import get_user_by_id
from .models import Post, PostImage, Tag, Like, Comment


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
            # Create the post
            post = Post.objects.create(user=user, **validated_data)

            # Create or fetch tags and associate them with the post
            for tag_name in tags_data:
                tag, _ = Tag.objects.get_or_create(name=tag_name.strip())
                post.tags.add(tag)

            # Create post images
            for image_data in post_images_data:
                PostImage.objects.create(post=post, **image_data)

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

def get_post_by_id(post_id:int)-> Post:
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
        post = Post.objects.get(id=post_id)
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
        return Post.objects.filter(user=user).prefetch_related(
            'post_images',
            'tags',
            Prefetch('likes', queryset=Like.objects.select_related('user')),
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).order_by('-created_at')
    except DatabaseError as e:
        raise DatabaseError(f"Database error while fetching posts: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while fetching posts: {str(e)}")
    
    
def update_post(post, user, validated_data):
    """
    Update a post's text, privacy, tags, and images.
    Args:
        post (Post): The post instance to update.
        user (User): The authenticated user.
        validated_data (dict): Validated data containing fields to update.
    Returns:
        Post: The updated post instance.
    Raises:
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        with transaction.atomic():
            # Update text and privacy if provided
            if 'text' in validated_data:
                post.text = validated_data['text']
            if 'privacy' in validated_data:
                post.privacy = validated_data['privacy']

            # Handle tags
            tags_to_add = validated_data.get('tags_to_add', [])
            tags_to_remove = validated_data.get('tags_to_remove', [])

            # Add new tags
            for tag_name in tags_to_add:
                tag, _ = Tag.objects.get_or_create(name=tag_name.strip())
                post.tags.add(tag)

            # Remove tags
            for tag_name in tags_to_remove:
                try:
                    tag = Tag.objects.get(name=tag_name.strip())
                    post.tags.remove(tag)
                except Tag.DoesNotExist:
                    pass  # Tag doesn't exist, skip

            # Handle images
            images_to_add = validated_data.get('post_images_to_add', [])
            images_to_remove = validated_data.get('post_images_to_remove', [])

            # Remove images
            if images_to_remove:
                PostImage.objects.filter(id__in=images_to_remove, post=post).delete()

            # Add new images
            for image_data in images_to_add:
                PostImage.objects.create(post=post, **image_data)

            # Save the post
            post.save()
            return post

    except DatabaseError as e:
        raise DatabaseError(f"Database error during post update: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error during post update: {str(e)}")
    
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
        
        print(f"requesting_user: {requesting_user.username}, target_user: {target_user.username}, target_user profile_type: {target_user.profile_type}, is_following: {is_following}, is_super_follower: {is_super_follower}", flush=True)

        # Public profile rules
        if target_user.profile_type =='public':
            print(f"public profile rules: {target_user.profile_type}", flush=True)
            if post.privacy == 'public':
                print(f"public post rules: {post.privacy}", flush=True)
                return True  # Anyone can like public posts on a public profile
            elif post.privacy == 'private':
                print(f"private post rules: {post.privacy}", flush=True)
                return is_super_follower  # Only super followers can like private posts
        
        # Private profile rules
        else:
            print(f"private profile rules: {target_user.profile_type}", flush=True)
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
        return Like.objects.filter(user=requesting_user, post=post).exists()
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
        
        print(f"requesting_user: {requesting_user.username}, target_user: {target_user.username}, target_user profile_type: {target_user.profile_type}, is_following: {is_following}, is_super_follower: {is_super_follower}", flush=True)

        # Allow commenting on own posts
        if requesting_user == target_user:
            return True

        # Public profile rules
        if target_user.profile_type == 'public':
            print(f"public profile rules: {target_user.profile_type}", flush=True)
            if post.privacy == 'public':
                print(f"public post rules: {post.privacy}", flush=True)
                return True  # Anyone can comment on public posts on a public profile
            elif post.privacy == 'private':
                print(f"private post rules: {post.privacy}", flush=True)
                return is_super_follower  # Only super followers can comment on private posts
        
        # Private profile rules
        else:
            print(f"private profile rules: {target_user.profile_type}", flush=True)
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
        return Comment.objects.filter(user=requesting_user, post=post).exists()
    except DatabaseError as e:
        raise DatabaseError(f"Database error while checking Comment existence: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while checking Comment existence: {str(e)}")