from django.db import DatabaseError, transaction
from django.db.models import Prefetch
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
    
    
def get_post_by_id(post_id, user):
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