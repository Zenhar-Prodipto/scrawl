from datetime import datetime
from django.db import DatabaseError, transaction
from django.db.models import Prefetch
from follows.services import check_follow_status, check_super_follower
from follows.services import FollowService
from users.models import User
from users.services import UserService
from .models import Post, PostImage, Tag, Like, Comment, Save
from scrawl.core.messaging import event_publisher
from scrawl.core.caching import cache_manager, invalidate
from django.conf import settings
from scrawl.core.monitoring.metrics.collectors import record_post_creation

class PostService:
    @classmethod
    def create_post(cls, user, validated_data, tags_data):
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
                record_post_creation(post.privacy, 'free')  

                for tag_name in tags_data:
                    tag, _ = Tag.objects.get_or_create(name=tag_name.strip())
                    post.tags.add(tag)

                for image_data in post_images_data:
                    PostImage.objects.create(post=post, **image_data)
                    
                event_publisher.publish_post_event(
                    'post_created', 
                    post_id=post.id,
                    user_id=user.id,
                    privacy=post.privacy,
                    created_at=post.created_at.isoformat()
                )

                # Invalidate caches
                invalidate.invalidate_post_cache(post_id=post.id,user_id=user.id)
                print("Cache invalidated for post and user posts:", post.id, user.id, flush=True)

                return post
        except DatabaseError as e:
            raise DatabaseError(f"Database error during post creation: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error during post creation: {str(e)}")
    
    @classmethod
    def get_self_post_by_id(cls, post_id, user):
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

    @classmethod
    def get_post_by_id(cls, post_id: int) -> Post:
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
            cached = cache_manager.get('post_detail', post_id=post_id)
            if cached is not None:
                print("Cache hit for post:", post_id, flush=True)
                return cached
            post = Post.objects.prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).get(id=post_id)
            cache_manager.set(key_type='post_detail',value= post, post_id=post_id)
            print("Cache miss for post:", post_id, flush=True)
            return post
        except Post.DoesNotExist:
            raise Post.DoesNotExist("Post not found.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error while fetching post: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while fetching post: {str(e)}")
    
    @classmethod
    def get_user_posts(cls, user):
        """
        Fetch all posts for the authenticated user (own posts).
        """
        try:
            # Check cache first
            cached = cache_manager.get('post_list', user_id=user.id)
            if cached is not None:
                print("Cache hit for user posts:", user.id, flush=True)
                return cached  
                
            # Database query if cache miss
            posts = Post.objects.filter(user=user).prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).order_by('-created_at')
            
            # Convert to list for caching
            posts_list = list(posts)
            
            # Cache the full objects
            cache_manager.set('post_list', posts_list, user_id=user.id)
            print("Cache miss for user posts:", user.id, flush=True)
            return posts_list
            
        except DatabaseError as e:
            raise DatabaseError(f"Database error while fetching posts: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while fetching posts: {str(e)}")
    

    @classmethod
    def update_post(cls, post, user, validated_data):
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
                
                event_publisher.publish_post_event(
                    'post_updated',
                    post_id=post.id,
                    user_id=user.id, 
                    privacy=post.privacy,
                    created_at=post.updated_at.isoformat() if hasattr(post, 'updated_at') else post.created_at.isoformat()
                )

                # Invalidate caches
                invalidate.invalidate_post_cache(post_id=post.id, user_id=user.id)
                print("Cache invalidated for post and user posts:", post.id, user.id, flush=True)

                return post
        except DatabaseError as e:
            raise DatabaseError(f"Database error during post update: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error during post update: {str(e)}")
    
    
    @classmethod
    def delete_post(cls, post, user):
        """
        Delete a post.
        """
        try:
            with transaction.atomic():
                if post.user != user:
                    raise Post.DoesNotExist("You do not have permission to delete this post.")
                post_id = post.id
                post.delete()

                event_publisher.publish_post_event(
                    'post_deleted',
                    post_id=post_id,
                    user_id=user.id
                )

                # Invalidate caches
                invalidate.invalidate_post_cache(post_id=post_id, user_id=user.id)
                print("Cache invalidated for post and user posts:", post_id, user.id, flush=True)
        except DatabaseError as e:
            raise DatabaseError(f"Database error during post deletion: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error during post deletion: {str(e)}")
    
    @classmethod
    def check_like_eligibility(cls, requesting_user, post):
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
            target_user_exists = UserService.get_user_by_id(target_user.id)
            if not target_user_exists:
                raise User.DoesNotExist("Target user does not exist or has been deleted.")
            
            # Allow Liking on own posts
            if requesting_user == target_user:
                return True

            # Check follow status and super follower status
            is_following = FollowService.check_follow_status(requesting_user, target_user.id)
            is_super_follower = FollowService.check_super_follower(requesting_user, target_user)
            
            # Public profile rules
            if target_user.profile_type == 'public':
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
    
    @classmethod
    def create_like(cls, requesting_user, post):
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
                
                event_publisher.publish_like_event(
                    'like_created',
                    user_id=requesting_user.id,
                    post_id=post.id,
                    created_at=like.created_at.isoformat()  
                )
                # Invalidate caches
                invalidate.invalidate_interaction_cache(user_id=requesting_user.id,post_id=post.id, interaction_type='like')
                print("Cache invalidated for post and like status:", post.id, requesting_user.id, flush=True)

                return like
        except DatabaseError as e:
            raise DatabaseError(f"Database error while creating like: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while creating like: {str(e)}")
    
    @classmethod
    def delete_like(cls, requesting_user, post):
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
                    invalidate.invalidate_interaction_cache(user_id=requesting_user.id, post_id=post.id, interaction_type='like')
                    print("Cache invalidated for post and like status:", post.id, requesting_user.id, flush=True)
        except DatabaseError as e:
            raise DatabaseError(f"Database error while deleting like: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while deleting like: {str(e)}")
    
    
    @classmethod
    def check_if_like_exists(cls, requesting_user, post):
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
            cached = cache_manager.get('like_exists', user_id=requesting_user.id, post_id=post.id)
            if cached is not None:
                print("Cache hit for like existence:", requesting_user.id, post.id)
                return cached
            status = Like.objects.filter(user=requesting_user, post=post).exists()
            cache_manager.set('like_exists', status, user_id=requesting_user.id, post_id=post.id)
            print("Cache miss for like existence:", requesting_user.id, post.id, flush=True)
            return status
        except DatabaseError as e:
            raise DatabaseError(f"Database error while checking like existence: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while checking like existence: {str(e)}")
    
    @classmethod
    def check_comment_eligibility(cls, requesting_user, post):
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
            target_user_exists = UserService.get_user_by_id(target_user.id)
            if not target_user_exists:
                raise User.DoesNotExist("Target user does not exist or has been deleted.")

            # Check follow status and super follower status
            is_following = FollowService.check_follow_status(requesting_user, target_user.id)
            is_super_follower = FollowService.check_super_follower(requesting_user, target_user)
            
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

    @classmethod
    def create_comment(cls, requesting_user, post, text):
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
                invalidate.invalidate_interaction_cache(user_id=requesting_user.id, post_id=post.id, interaction_type='comment')
                print("Cache invalidated for post and comment status:", post.id, requesting_user.id, flush=True)

                return comment
        except DatabaseError as e:
            raise DatabaseError(f"Database error while creating comment: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while creating comment: {str(e)}")
    
    @classmethod
    def check_if_comment_exists(cls, requesting_user, post):
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
            cached = cache_manager.get('comment_exists', user_id=requesting_user.id, post_id=post.id)
            if cached is not None:
                print("Cache hit for comment existence:", requesting_user.id, post.id, flush=True)
                return cached
            status = Comment.objects.filter(user=requesting_user, post=post).exists()
            cache_manager.set('comment_exists', status, user_id=requesting_user.id, post_id=post.id)
            print("Cache miss for comment existence:", requesting_user.id, post.id, flush=True)
            return status
        except DatabaseError as e:
            raise DatabaseError(f"Database error while checking Comment existence: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while checking Comment existence: {str(e)}")
    
    @classmethod
    def update_comment(cls, comment, text):
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
    
    @classmethod
    def get_comment_by_id(cls, comment_id: int, post: Post) -> Comment:
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
    
    
    @classmethod
    def delete_comment(cls, comment):
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
                invalidate.invalidate_interaction_cache(user_id=comment.user.id, post_id=post.id, interaction_type='comment')
                print("Cache invalidated for post and comment status:", post.id, comment.user.id, flush=True)
        except DatabaseError as e:
            raise DatabaseError(f"Database error while deleting comment: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while deleting comment: {str(e)}")
    
    @classmethod
    def get_save_by_user_and_post(cls, user, post):
        try:
            save = Save.objects.get(user=user, post=post)
            return save
        except Save.DoesNotExist:
            return None
        except DatabaseError as e:
            raise DatabaseError(f"Database error while fetching save: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while fetching save: {str(e)}")

    @classmethod
    def create_save(cls, user, post):
        try:
            with transaction.atomic():
                save = Save.objects.create(user=user, post=post)

                # Invalidate caches
                invalidate.invalidate_interaction_cache(user_id=user.id, post_id=post.id, interaction_type='save')
                print("Cache invalidated for saved posts and post:", user.id, post.id, flush=True)

                return save
        except DatabaseError as e:
            raise DatabaseError(f"Database error while creating save: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while creating save: {str(e)}")

    @classmethod
    def delete_save(cls, user, post):
        try:
            with transaction.atomic():
                save = cls.get_save_by_user_and_post(user, post)
                if save:
                    save.delete()

                    # Invalidate caches
                    invalidate.invalidate_interaction_cache(user_id=user.id, post_id=post.id, interaction_type='save')
                    print("Cache invalidated for saved posts and post:", user.id, post.id, flush=True)
        except DatabaseError as e:
            raise DatabaseError(f"Database error while deleting save: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while deleting save: {str(e)}")
    
    @classmethod
    def check_save_eligibility(cls, requesting_user, post):
        try:
            target_user = post.user
            
            # Check if the target user exists and is not deleted
            target_user_exists = UserService.get_user_by_id(target_user.id)
            if not target_user_exists:
                raise User.DoesNotExist("Target user does not exist or has been deleted.")

            # Check follow status and super follower status
            is_following = FollowService.check_follow_status(requesting_user, target_user.id)
            is_super_follower = FollowService.check_super_follower(requesting_user, target_user)
            
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
    
    @classmethod
    def get_user_saved_posts(cls, user):
        try:
            cached = cache_manager.get('post_saved', user_id=user.id)
            if cached is not None:
                print("Cache hit for saved posts:", user.id, flush=True)
                return cached

            saved_posts = Post.objects.filter(saves__user=user).prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).order_by('-created_at')
            saved_posts_list = list(saved_posts)
            cache_manager.set('post_saved', saved_posts_list, user_id=user.id)
            print("Cache miss for saved posts:", user.id, flush=True)
            return saved_posts_list
        except DatabaseError as e:
            raise DatabaseError(f"Database error while fetching saved posts: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while fetching saved posts: {str(e)}")
    
    @classmethod
    def get_user_posts_by_id(cls, user_id: int):
        """
        Fetch all posts for a specified user ID (viewing another user's profile).
        """
        try:
            # Verify user exists first
            user = User.objects.get(id=user_id, is_deleted=False)
            
            # Check cache first
            cached = cache_manager.get('post_user_posts', user_id=user_id)
            if cached is not None:
                print("Cache hit for user posts:", user_id, flush=True)
                return cached  
                
            # Database query if cache miss
            posts = Post.objects.filter(user=user).prefetch_related(
                'post_images',
                'tags',
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('user'))
            ).order_by('-created_at')
            
            # Convert to list for caching
            posts_list = list(posts)
            
            # Cache the full objects
            cache_manager.set('post_user_posts', posts_list, user_id=user_id)
            print("Cache miss for user posts:", user_id, flush=True)
            return posts_list
            
        except User.DoesNotExist:
            raise User.DoesNotExist("User not found.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error while fetching posts: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error while fetching posts: {str(e)}")

    @classmethod
    def post_view_eligibility(cls, requesting_user: User, post: Post) -> bool:
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
            target_user_exists = UserService.get_user_by_id(target_user.id)
            if not target_user_exists:
                raise User.DoesNotExist("Target user does not exist or has been deleted.")

            # Allow viewing own posts
            if requesting_user == target_user:
                return True

            # Check follow status and super follower status
            is_following = FollowService.check_follow_status(requesting_user, target_user.id)
            is_super_follower = FollowService.check_super_follower(requesting_user, target_user)
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

# Backward compatibility
create_post = PostService.create_post
get_self_post_by_id = PostService.get_self_post_by_id
get_post_by_id = PostService.get_post_by_id
get_user_posts = PostService.get_user_posts
update_post = PostService.update_post
delete_post = PostService.delete_post
check_like_eligibility = PostService.check_like_eligibility
create_like = PostService.create_like
delete_like = PostService.delete_like
check_if_like_exists = PostService.check_if_like_exists
check_comment_eligibility = PostService.check_comment_eligibility
create_comment = PostService.create_comment
check_if_comment_exists = PostService.check_if_comment_exists
update_comment = PostService.update_comment
get_comment_by_id = PostService.get_comment_by_id
delete_comment = PostService.delete_comment
get_save_by_user_and_post = PostService.get_save_by_user_and_post
create_save = PostService.create_save
delete_save = PostService.delete_save
check_save_eligibility = PostService.check_save_eligibility
get_user_saved_posts = PostService.get_user_saved_posts
get_user_posts_by_id = PostService.get_user_posts_by_id
post_view_eligibility = PostService.post_view_eligibility
