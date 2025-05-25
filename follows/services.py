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