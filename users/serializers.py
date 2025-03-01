from rest_framework import serializers
from .models import User, Interest

class InterestSerializer(serializers.ModelSerializer):
    """
    Serializer for Interest model to display interest details.
    """
    class Meta:
        model = Interest
        fields = ['id', 'name']

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model to display user profile data.
    """
    interests = InterestSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile_picture', 'interests']
        read_only_fields = ['id']