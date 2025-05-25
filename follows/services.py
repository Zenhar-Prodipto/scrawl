from follows.models import Follow, FollowRequest
from users.models import User
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist

def follow_user(user: User, target_id: int) -> Follow:
    try:
        target_user = User.objects.get(id=target_id, is_deleted=False)
        follow, created = Follow.objects.get_or_create(follower=user, followed=target_user)
        if not created:
            raise ValueError("You already follow this user.")
        return follow
    except User.DoesNotExist:  
        raise User.DoesNotExist("Target user does not exist.")  
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def unfollow_user(user: User, target_id: int) -> None:
    try:
        target = User.objects.get(id=target_id, is_deleted=False)
        Follow.objects.filter(follower=user, followed=target).delete()
    except User.DoesNotExist:  # Specific
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def get_followers(user_id:int)->list[User]:
    try:
        user = User.objects.get(id=user_id, is_deleted=False)
        follow_relationships = user.followers.all()  # Queryset of Follow objects
        # Extract the follower users
        followers = User.objects.filter(id__in=follow_relationships.values('follower_id'), is_deleted=False)
        return followers
        return followers
    except User.DoesNotExist:  # Specific
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def get_following(user_id:int)->list[User]:
    try:
        user = User.objects.get(id=user_id, is_deleted=False)
        follow_relationships = user.following.all()  # Queryset of Follow objects
        # Extract the followed users
        following = User.objects.filter(id__in=follow_relationships.values('followed_id'), is_deleted=False)
        return following
    except User.DoesNotExist:  # Specific
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:  
        raise DatabaseError(f"Database error: {str(e)}")
    
def check_follow_status(current_user: User, target_id: int) -> bool:
    try:
        target_user = User.objects.get(id=target_id, is_deleted=False)
        return Follow.objects.filter(follower=current_user, followed=target_user).exists()
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
    
def follow_requests_incoming(target:User) -> list[FollowRequest]:
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
    
    
def follow_requests_outgoing(requester:User) -> list[FollowRequest]:
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