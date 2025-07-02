from datetime import datetime
from follows.models import Follow, FollowRequest
from users.models import User
from django.db import DatabaseError, transaction
from django.core.exceptions import ObjectDoesNotExist
from scrawl.config.kafka_config import producer, delivery_report
import json
import redis
from django.conf import settings

# Redis client
redis_client = redis.Redis.from_url(settings.REDIS_URL)

# Cache keys
FOLLOWERS_CACHE_KEY = "followers:{user_id}"
FOLLOWING_CACHE_KEY = "following:{user_id}"
FOLLOW_STATUS_CACHE_KEY = "follow_status:{user_id}:{target_id}"

def follow_user(user: User, target_id: int) -> Follow:
    try:
        target_user = User.objects.get(id=target_id, is_deleted=False)
        follow, created = Follow.objects.get_or_create(follower=user, followed=target_user)
        if not created:
            raise ValueError("You already follow this user.")
        
        # Publish follow event
        event = {
            "event_type": "follow.created",
            "follower_id": user.id,
            "followed_id": target_user.id,
            "created_at": follow.created_at.isoformat(),
            "is_super_follower": follow.is_super_follower
        }
        producer.produce(
            "follow.events",
            value=json.dumps(event).encode('utf-8'),
            callback=delivery_report
        )
        producer.flush()  # Ensure delivery for simplicity (remove in prod for async)
        
        # Invalidate caches
        redis_client.delete(FOLLOWERS_CACHE_KEY.format(user_id=target_user.id))
        redis_client.delete(FOLLOWING_CACHE_KEY.format(user_id=user.id))
        redis_client.delete(FOLLOW_STATUS_CACHE_KEY.format(user_id=user.id, target_id=target_user.id))
        
        return follow
    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def unfollow_user(user: User, target_id: int) -> None:
    try:
        target_user = User.objects.get(id=target_id, is_deleted=False)
        with transaction.atomic():
            deleted_count, _ = Follow.objects.filter(follower=user, followed=target_user).delete()
            if deleted_count == 0:
                raise ValueError("You are not following this user.")
            
            # Publish unfollow event
            event = {
                "event_type": "follow.deleted",
                "follower_id": user.id,
                "followed_id": target_user.id,
                "created_at": datetime.now().isoformat()
            }
            producer.produce(
                "follow.events",
                value=json.dumps(event).encode('utf-8'),
                callback=delivery_report
            )
            producer.flush()  # Ensure delivery (remove in prod)
        
        # Invalidate caches
        redis_client.delete(FOLLOWERS_CACHE_KEY.format(user_id=target_user.id))
        redis_client.delete(FOLLOWING_CACHE_KEY.format(user_id=user.id))
        redis_client.delete(FOLLOW_STATUS_CACHE_KEY.format(user_id=user.id, target_id=target_user.id))
        print("Cache invalidated for follower/following/status:", target_user.id, user.id,flush=True)
    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def get_followers(user_id: int) -> list[User]:
    try:
        cache_key = FOLLOWERS_CACHE_KEY.format(user_id=user_id)
        cached_followers = redis_client.get(cache_key)
        if cached_followers:
            print("Cache hit for followers:", user_id,flush=True)
            follower_ids = json.loads(cached_followers)
            return list(User.objects.filter(id__in=follower_ids, is_deleted=False))
        user = User.objects.get(id=user_id, is_deleted=False)
        follow_relationships = user.followers.all()
        followers = list(User.objects.filter(id__in=follow_relationships.values('follower_id'), is_deleted=False))
        redis_client.setex(cache_key, 300, json.dumps([f.id for f in followers]))  # 5m TTL
        print("Cache miss for followers:", user_id,flush=True)
        return followers
    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def get_following(user_id: int) -> list[User]:
    try:
        cache_key = FOLLOWING_CACHE_KEY.format(user_id=user_id)
        cached_following = redis_client.get(cache_key)
        if cached_following:
            print("Cache hit for following:", user_id,flush=True)
            following_ids = json.loads(cached_following)
            return list(User.objects.filter(id__in=following_ids, is_deleted=False))
        user = User.objects.get(id=user_id, is_deleted=False)
        follow_relationships = user.following.all()
        following = list(User.objects.filter(id__in=follow_relationships.values('followed_id'), is_deleted=False))
        redis_client.setex(cache_key, 300, json.dumps([f.id for f in following]))  # 5m TTL
        print("Cache miss for following:", user_id,flush=True)
        return following
    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def check_follow_status(current_user: User, target_id: int) -> bool:
    try:
        cache_key = FOLLOW_STATUS_CACHE_KEY.format(user_id=current_user.id, target_id=target_id)
        cached_status = redis_client.get(cache_key)
        if cached_status:
            print("Cache hit for follow status:", current_user.id, target_id,flush=True)
            return json.loads(cached_status)
        target_user = User.objects.get(id=target_id, is_deleted=False)
        status = Follow.objects.filter(follower=current_user, followed=target_user).exists()
        redis_client.setex(cache_key, 60, json.dumps(status))  # 1m TTL
        print("Cache miss for follow status:", current_user.id, target_id,flush=True)
        return status
    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def check_super_follower(requesting_user: User, target_user: User) -> bool:
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
    
def get_follower_count(user_id: int) -> int:
    try:
        user = User.objects.get(id=user_id, is_deleted=False)
        return user.followers.count()
    except User.DoesNotExist:
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def get_following_count(user_id: int) -> int:    
    try:    
        user = User.objects.get(id=user_id, is_deleted=False)
        return user.following.count()
    except User.DoesNotExist:                
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def does_follow_request_exist(requester: User, target_id: int) -> bool:
    try:
        target_user = User.objects.get(id=target_id, is_deleted=False)
        return FollowRequest.objects.filter(
            requester=requester,
            target=target_user,
            status='pending'
        ).exists()
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")

def create_follow_request(requester: User, target_id: int) -> FollowRequest:
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
    
def follow_requests_incoming(target: User) -> list[FollowRequest]:
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
    
    
def follow_requests_outgoing(requester: User) -> list[FollowRequest]:
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
    

def update_follow_request(current_user: User, req_id: int, new_status: str) -> None:
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
            # Reuse follow_user to create the follow relationship
            follow_user(follow_request.requester, follow_request.target.id)
            # Delete the FollowRequest
            follow_request.delete()
        else:  # new_status == 'denied'
            follow_request.status = 'denied'
            follow_request.save()

    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def cancel_follow_request(current_user: User, req_id: int) -> None:
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