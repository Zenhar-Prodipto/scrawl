from .models import User

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

from .models import User

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
    