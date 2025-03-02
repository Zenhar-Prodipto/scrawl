from rest_framework import serializers
from .models import User, Interest
from .services import create_user

class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ['id', 'name']

class UserSerializer(serializers.ModelSerializer):
    interests = InterestSerializer(many=True, read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_picture', 'interests']
        read_only_fields = ['id']

class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True, max_length=150)
    email = serializers.EmailField(required=True)  # Email type check built-in
    password = serializers.CharField(required=True, write_only=True, min_length=6)
    first_name = serializers.CharField(required=True, max_length=30)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name']
        
    def validate(self, data):
        # Check raw input before coercion
        raw_data = self.initial_data  # Original request data
        for field in ['username', 'email', 'first_name', 'last_name']:
            if field in raw_data and not isinstance(raw_data[field], str):
                raise serializers.ValidationError({field: "This field must be a string, not a number or other type."})
        return data

    def validate_username(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError("Username must be a string.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_first_name(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError("First name must be a string.")
        return value

    def validate_last_name(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError("Last name must be a string.")
        return value

    def create(self, validated_data):
        return create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )