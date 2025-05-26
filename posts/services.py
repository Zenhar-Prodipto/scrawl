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