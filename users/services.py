from .models import User, Interest
from django.db import DatabaseError
from django.utils import timezone
def create_user(username,email,password,first_name,last_name):
    """
    Create a new user with the given credentials.
    """
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name
    )
    return user


def get_user_by_id(user_id):
    return User.objects.get(id=user_id)

def get_user_by_email(email):
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        return None

def get_user_by_username(username):
    return User.objects.get(username=username)

def match_password(user, password):
    return user.check_password(password) 


def update_user(user: User, validated_data: dict) -> User:
    """
    Update a User instance with validated data.
    Handles fields and interests delta. Returns updated user.
    """
    try:
        print("Validated Data from service layer",validated_data,flush=True)
        # Update regular fields if present
        if 'username' in validated_data:
            user.username = validated_data['username']
        if 'first_name' in validated_data:
            user.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            user.last_name = validated_data['last_name']
        if 'profile_picture' in validated_data:
            user.profile_picture = validated_data['profile_picture']

        # Handle interests delta
        interests_data = validated_data.get('interests', {})
        if 'add' in interests_data and interests_data['add']:
            user.interests.add(*interests_data['add'])
        if 'remove' in interests_data and interests_data['remove']:
            user.interests.remove(*interests_data['remove'])

        # Save the user
        user.save()
        return user

    except Interest.DoesNotExist:
        raise ValueError("One or more interest IDs do not exist.")
    except DatabaseError as e:
        raise DatabaseError(f"Database error during update: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error during update: {str(e)}")
    
def soft_delete_user(user:User)->User:
    try:
        user.is_deleted = True
        user.deleted_at  =timezone.now()
        user.save()
        return user 
    except DatabaseError as e:
        raise DatabaseError(f"Database error during soft delete: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error during soft delete: {str(e)}")
        

def get_interests():
    return Interest.objects.all()
    