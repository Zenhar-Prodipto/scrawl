from follows.models import Follow
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
        followers = User.objects.filter(following__followed=user, is_deleted=False)
        return followers
    except User.DoesNotExist:  # Specific
        raise User.DoesNotExist("Target user does not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error: {str(e)}")
    
def get_following(user_id:int)->list[User]:
    try:
        user = User.objects.get(id=user_id, is_deleted=False)
        following = User.objects.filter(following__follower=user, is_deleted=False)
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