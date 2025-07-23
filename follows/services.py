from datetime import datetime
from follows.models import Follow, FollowRequest
from users.models import User
from django.db import DatabaseError, transaction
from django.core.exceptions import ObjectDoesNotExist
from scrawl.core.messaging import event_publisher
from scrawl.core.caching import cache_manager, invalidate

class FollowService:
    @classmethod
    def follow_user(cls, user: User, target_id: int) -> Follow:
        try:
            target_user = User.objects.get(id=target_id, is_deleted=False)
            follow, created = Follow.objects.get_or_create(follower=user, followed=target_user)
            if not created:
                raise ValueError("You already follow this user.")
            
            event_publisher.publish_follow_event(
                'follow_created',
                follower_id=user.id,
                followed_id=target_user.id,
                is_super_follower=follow.is_super_follower,
                created_at=follow.created_at.isoformat()
            )
            # Invalidate caches
            invalidate.invalidate_follow_relationship_cache(user.id, target_user.id)

            
            return follow
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def unfollow_user(cls, user: User, target_id: int) -> None:
        try:
            target_user = User.objects.get(id=target_id, is_deleted=False)
            with transaction.atomic():
                      
                follow = Follow.objects.filter(follower=user, followed=target_user).first()
                if not follow:
                    raise ValueError("You are not following this user.")
            
                # Store the original follow data before deletion
                original_is_super_follower = follow.is_super_follower
                original_created_at = follow.created_at.isoformat()
            
                # Delete the follow relationship
                deleted_count, _ = Follow.objects.filter(follower=user, followed=target_user).delete()
                if deleted_count == 0:
                    raise ValueError("You are not following this user.")
            
            # Publish unfollow event 
                event_publisher.publish_follow_event(
                    'follow_deleted',
                    follower_id=user.id,
                    followed_id=target_user.id,
                    is_super_follower=original_is_super_follower,  
                    created_at=original_created_at  
                )
                
            
            invalidate.invalidate_follow_relationship_cache(user.id, target_user.id)
            print("Cache invalidated for follower/following/status:", target_user.id, user.id, flush=True)
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def get_followers(cls, user_id: int) -> list[User]:
        try:
            cached = cache_manager.get('user_followers', user_id=user_id)
            if cached is not None:
                print("Cache hit for followers:", user_id, flush=True)
                return list(User.objects.filter(id__in=cached, is_deleted=False))
            user = User.objects.get(id=user_id, is_deleted=False)
            follow_relationships = user.followers.all()
            followers = list(User.objects.filter(id__in=follow_relationships.values('follower_id'), is_deleted=False))
            cache_manager.set('user_followers', [f.id for f in followers], user_id=user_id)
            print("Cache miss for followers:", user_id, flush=True)
            return followers
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def get_following(cls, user_id: int) -> list[User]:
        try:
            cached = cache_manager.get('user_following', user_id=user_id)
            if cached is not None:
                print("Cache hit for following:", user_id, flush=True)
                return list(User.objects.filter(id__in=cached, is_deleted=False))
            user = User.objects.get(id=user_id, is_deleted=False)
            follow_relationships = user.following.all()
            following = list(User.objects.filter(id__in=follow_relationships.values('followed_id'), is_deleted=False))
            cache_manager.set('user_following', [f.id for f in following], user_id=user_id)
            print("Cache miss for following:", user_id, flush=True)
            return following
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def check_follow_status(cls, current_user: User, target_id: int) -> bool:
        try:
            cached = cache_manager.get('follow_exists', follower_id=current_user.id, followed_id=target_id)
            if cached is not None:  
                print("Cache hit for follow status:", current_user.id, target_id, flush=True)
                return cached
            target_user = User.objects.get(id=target_id, is_deleted=False)
            status = Follow.objects.filter(follower=current_user, followed=target_user).exists()
            cache_manager.set('follow_exists', status, follower_id=current_user.id, followed_id=target_id)
            print("Cache miss for follow status:", current_user.id, target_id, flush=True)
            return status
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def check_super_follower(cls, requesting_user: User, target_user: User) -> bool:
        try:
            is_super_follower = Follow.objects.filter(
                follower=requesting_user,
                followed=target_user,
                is_super_follower=True
            ).exists()
            return is_super_follower
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def get_follower_count(cls, user_id: int) -> int:
        try:
            user = User.objects.get(id=user_id, is_deleted=False)
            return user.followers.count()
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def get_following_count(cls, user_id: int) -> int:
        try:
            user = User.objects.get(id=user_id, is_deleted=False)
            return user.following.count()
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def does_follow_request_exist(cls, requester: User, target_id: int) -> bool:
        try:
            target_user = User.objects.get(id=target_id, is_deleted=False)
            return FollowRequest.objects.filter(
                requester=requester,
                target=target_user,
                status='pending'
            ).exists()
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")

    @classmethod
    def create_follow_request(cls, requester: User, target_id: int) -> FollowRequest:
        try:
            target_user = User.objects.get(id=target_id, is_deleted=False)
            follow_request = FollowRequest.objects.create(
                requester=requester,
                target=target_user,
                status='pending'
            )
            return follow_request
        except User.DoesNotExist:
            raise User.DoesNotExist("Target user does not exist.")
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def follow_requests_incoming(cls, target: User) -> list[FollowRequest]:
        """
        Fetch all pending follow requests where the user is the target.
        Args:
            target (User): The user receiving the follow requests.
        Returns:
            list[FollowRequest]: Queryset of pending follow requests.
        """
        try:
            follow_requests = FollowRequest.objects.filter(
                target=target,
                status='pending'
            ).order_by('created_at')
            return follow_requests
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def follow_requests_outgoing(cls, requester: User) -> list[FollowRequest]:
        """
        Fetch all pending follow requests sent by the user.
        Args:
            requester (User): The user who sent the follow requests.
        Returns:
            list[FollowRequest]: Queryset of pending follow requests.
        """
        try:
            follow_requests = FollowRequest.objects.filter(
                requester=requester,
                status='pending'
            ).order_by('created_at')
            return follow_requests
        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def update_follow_request(cls, current_user: User, req_id: int, new_status: str) -> None:
        """
        Update the status of a follow request (accept/deny).
        Args:
            current_user (User): The user attempting to update the request.
            req_id (int): The ID of the FollowRequest to update.
            new_status (str): Either 'accepted' or 'denied'.
        Raises:
            ValueError: If the request doesn't exist, user is unauthorized, or request isn't pending.
            DatabaseError: If a database error occurs.
        """
        try:
            # Fetch the follow request
            follow_request = FollowRequest.objects.filter(id=req_id).first()
            if not follow_request:
                raise ValueError("Follow request does not exist.")

            # Check if the current user is the target
            if follow_request.target != current_user:
                raise ValueError("You are not authorized to update this request.")

            # Check if the request is pending
            if follow_request.status != 'pending':
                raise ValueError("This request cannot be updated as it is not pending.")

            if new_status == 'accepted':
                cls.follow_user(follow_request.requester, follow_request.target.id)
                # Delete the FollowRequest
                follow_request.delete()
            else:  
                follow_request.status = 'denied'
                follow_request.save()

        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")
    
    @classmethod
    def cancel_follow_request(cls, current_user: User, req_id: int) -> None:
        """
        Cancel the outgoing follow request.
        Args:
            current_user (User): The user attempting to cancel the request.
            req_id (int): The ID of the FollowRequest to update.
        Raises:
            ValueError: If the request doesn't exist, user is unauthorized, or request isn't pending.
            DatabaseError: If a database error occurs.
        """
        try:
            # Fetch the follow request
            follow_request = FollowRequest.objects.filter(id=req_id).first()
            if not follow_request:
                raise ValueError("Follow request does not exist.")

            # Check if the current user is the requester
            if follow_request.requester != current_user:
                raise ValueError("You are not authorized to cancel this request.")

            # Check if the request is pending
            if follow_request.status != 'pending':
                raise ValueError("This request cannot be cancelled as it is not pending.")

            follow_request.status = 'cancelled'
            follow_request.save()

        except DatabaseError as e:
            raise DatabaseError(f"Database error: {str(e)}")

# Backward compatibility
follow_user = FollowService.follow_user
unfollow_user = FollowService.unfollow_user
get_followers = FollowService.get_followers
get_following = FollowService.get_following
check_follow_status = FollowService.check_follow_status
check_super_follower = FollowService.check_super_follower
get_follower_count = FollowService.get_follower_count
get_following_count = FollowService.get_following_count
does_follow_request_exist = FollowService.does_follow_request_exist
create_follow_request = FollowService.create_follow_request
follow_requests_incoming = FollowService.follow_requests_incoming
follow_requests_outgoing = FollowService.follow_requests_outgoing
update_follow_request = FollowService.update_follow_request
cancel_follow_request = FollowService.cancel_follow_request