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