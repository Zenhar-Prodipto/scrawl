from rest_framework import serializers
from .models import Follow
from users.models import User

class FollowSerializer(serializers.ModelSerializers):
    class Meta:
        model = Follow
        fields = ['followed']  # Only need followed user ID for input
        extra_kwargs = {'followed': {'required': True}} 
    
    def validate_followed(self,value):
        user = self.context['request'].user
        if value == user:
            raise serializers.ValidationError("You cannot follow yourself.")
        return value 
    
class UserFollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_picture']
        
        