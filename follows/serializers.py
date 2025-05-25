from rest_framework import serializers
from .models import Follow, FollowRequest
from users.models import User

class FollowSerializer(serializers.ModelSerializer):
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
        fields = ['id', 'username', 'first_name', 'last_name', 'profile_picture','bio']
        
class SelfUserFollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'profile_picture','bio','profile_type']
        
class FollowRequestSerializerIncoming(serializers.ModelSerializer):
    requester = serializers.PrimaryKeyRelatedField(read_only=True)
    target = serializers.PrimaryKeyRelatedField(read_only=True)
    requester_details = UserFollowSerializer(source='requester', read_only=True)  # Nested user data

    class Meta:
        model = FollowRequest
        fields = ['id', 'requester', 'target', 'status', 'created_at', 'updated_at', 'requester_details']
        
class FollowRequestSerializerOutgoing(serializers.ModelSerializer):
    requester = serializers.PrimaryKeyRelatedField(read_only=True)
    target = serializers.PrimaryKeyRelatedField(read_only=True)
    target_details = UserFollowSerializer(source='target', read_only=True)  # Nested user data

    class Meta:
        model = FollowRequest
        fields = ['id', 'requester', 'target', 'status', 'created_at', 'updated_at', 'target_details']