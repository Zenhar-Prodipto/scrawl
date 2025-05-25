from  follows.services import follow_requests_incoming, follow_user
from .models import User, Interest
from follows.models import Follow, FollowRequest
from django.db import DatabaseError,transaction
from django.utils import timezone
def create_user(username,email,password,first_name,last_name,profile_type='public', bio=None):
    """
    Create a new user with the given credentials.
    """
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        profile_type=profile_type,
        bio=bio
    )
    return user


def get_user_by_id(user_id):
    try:
        return User.objects.get(id=user_id,is_deleted=False)
    except User.DoesNotExist:
        return None

def get_user_by_email(email):
    try:
        return User.objects.get(email=email,is_deleted=False)
    except User.DoesNotExist:
        return None

def get_user_by_username(username):
    try:
        return User.objects.get(username=username,is_deleted=False)
    except User.DoesNotExist:
        return None
def match_password(user, password):
    return user.check_password(password) 

    
def update_user(user: User, validated_data: dict) -> User:
    """
    Update a User instance with validated data.
    Handles fields and interests delta. Converts pending follow requests to follows if profile_type
    changes from private to public.
    Args:
        user (User): The user to update.
        validated_data (dict): Validated data from the serializer.
    Returns:
        User: The updated user instance.
    Raises:
        ValueError: If validation fails (e.g., invalid interests).
        DatabaseError: If a database error occurs.
        Exception: For unexpected errors.
    """
    try:
        print("Validated Data from service layer", validated_data, flush=True)
        # Track the original profile_type
        original_profile_type = user.profile_type

        # Update regular fields if present
        if 'username' in validated_data:
            user.username = validated_data['username']
        if 'first_name' in validated_data:
            user.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            user.last_name = validated_data['last_name']
        if 'profile_picture' in validated_data:
            user.profile_picture = validated_data['profile_picture']
        if 'bio' in validated_data:
            user.bio = validated_data['bio']
        if 'profile_type' in validated_data:
            user.profile_type = validated_data['profile_type']

        # Handle interests delta
        interests_data = validated_data.get('interests', {})
        if 'add' in interests_data and interests_data['add']:
            user.interests.add(*interests_data['add'])
        if 'remove' in interests_data and interests_data['remove']:
            user.interests.remove(*interests_data['remove'])

        # Save the user
        user.save()

        # Check if profile_type changed from private to public
        if 'profile_type' in validated_data and original_profile_type == 'private' and validated_data['profile_type'] == 'public':
            # Fetch all pending follow requests where this user is the target
            pending_requests = follow_requests_incoming(user)

            # Convert each pending request to a Follow entry
            for follow_request in pending_requests:
                try:
                    with transaction.atomic():  # Ensure atomicity
                        # Create a Follow entry using follow_user
                        follow_user(follow_request.requester, user.id)
                        # Delete the FollowRequest
                        follow_request.delete()
                except ValueError as e:
                    # Log the error but continue with other requests
                    print(f"Failed to convert follow request {follow_request.id}: {str(e)}", flush=True)
                except DatabaseError as e:
                    # Log the error but continue
                    print(f"Database error while converting follow request {follow_request.id}: {str(e)}", flush=True)

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
    