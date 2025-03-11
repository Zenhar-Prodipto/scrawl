from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
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
    interests = serializers.PrimaryKeyRelatedField(  # Links to Interest IDs
        many=True,
        queryset=Interest.objects.all(),
        required=True,
        help_text="List of interest IDs (e.g., [1, 2])"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name','interests']
        
    def validate(self, data):
        # Check raw input before coercion for strict validation
        raw_data = self.initial_data  # Original request data
        for field in ['username', 'email', 'first_name', 'last_name']:
            if field in raw_data and not isinstance(raw_data[field], str):
                raise serializers.ValidationError({field: "This field must be a string, not a number or other type."})
            
        if 'interests' not in raw_data:
            raise serializers.ValidationError({"interests": "This field is required."})
        if not isinstance(raw_data['interests'], list):
            raise serializers.ValidationError({"interests": "Interests must be a list of IDs (e.g., [1, 2])."})
        if len(raw_data['interests']) < 2:
            raise serializers.ValidationError({"interests": "You must select at least 2 interests."})
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
        interests = validated_data.pop('interests')
        user = create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        user.interests.set(interests)
        return user
    
    
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)
    
        
    # Validate function might look redundant but I'm being strict on raw data input 
    def validate(self,data):
        raw_data = self.initial_data
        if not isinstance(raw_data['email'],str) or not isinstance(raw_data['password'],str):
            raise serializers.ValidationError("Email and password must be strings.")
        return data
        
    def validate_email(self, value):
        if not isinstance(value, str):
             raise serializers.ValidationError("Email must be a string.")
            
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Invalid credentials")
        return value
    

class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(required=True)

    def validate(self, data):
        print(f"LogoutSerializer: Refresh={data['refresh_token']}", flush=True)
        if not isinstance(data['refresh_token'], str):
            raise serializers.ValidationError("Refresh token must be a string.")
        try:
            token = RefreshToken(data['refresh_token'])
            token.blacklist()
            print("LogoutSerializer: Token blacklisted", flush=True)
        except Exception as e:
            raise serializers.ValidationError(f"Invalid or expired refresh token: {str(e)}")
        return data
