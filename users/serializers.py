from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Interest
from .services import create_user, update_user

class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ['id', 'name']

class UserSerializer(serializers.ModelSerializer):
    interests = InterestSerializer(many=True, read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_picture', 'interests','is_deleted', 'deleted_at']
        read_only_fields = ['id','is_deleted', 'deleted_at']

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
    

class InterestDeltaSerializer(serializers.Serializer):
    add = serializers.ListField(child=serializers.IntegerField(), required=False)
    remove = serializers.ListField(child=serializers.IntegerField(), required=False)
    
    def validate(self, data):
        # No self.initial_data here - use data directly
        add = data.get('add', [])
        remove = data.get('remove', [])
        # Optional: Add custom validation
        if not isinstance(add, list) or not isinstance(remove, list):
            raise serializers.ValidationError("Both 'add' and 'remove' must be lists.")
        # Check if Interest IDs exist
        invalid_add = [id for id in add if not Interest.objects.filter(id=id).exists()]
        invalid_remove = [id for id in remove if not Interest.objects.filter(id=id).exists()]
        if invalid_add or invalid_remove:
            raise serializers.ValidationError({
                "add": f"Invalid interest IDs: {invalid_add}" if invalid_add else None,
                "remove": f"Invalid interest IDs: {invalid_remove}" if invalid_remove else None
            })
        return data
class UpdateUserSerializer(serializers.ModelSerializer):
    interests = InterestDeltaSerializer(required=False)
    username = serializers.CharField(required=False, allow_null=False, allow_blank=False)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'profile_picture', 'interests']
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'profile_picture': {'required': False},
        }
        
    def validate(self,data):
        raw_data = self.initial_data
        validated_data = {}
        for field in ['username', 'first_name', 'last_name']:
            if field in raw_data:
                if not isinstance(raw_data[field], str):
                    raise serializers.ValidationError({field: "This field must be a string."})
                validated_data[field] = raw_data[field]
        if 'profile_picture' in raw_data:
            if not isinstance(raw_data['profile_picture'], dict):
                raise serializers.ValidationError({"profile_picture": "This field must be a dictionary (e.g., {'full': 'url1', 'thumb': 'url2'})."})
            validated_data['profile_picture'] = raw_data['profile_picture']
        interests_serializer = InterestDeltaSerializer(data=raw_data['interests'])
        interests_serializer.is_valid(raise_exception=True)
        validated_data['interests'] = interests_serializer.validated_data
        print("Post-Validate Data:", validated_data, flush=True)
        return validated_data
    
    def validate_username(self,value):
        if not isinstance(value,str):
            raise serializers.ValidationError("Username must be a string.")
        user = self.instance # Current user being updated
        if User.objects.exclude(id=user.id).filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        
    def validate_first_name(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError("First name must be a string.")
        return value

    def validate_last_name(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError("Last name must be a string.")
        return value

    def validate_profile_picture(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Profile picture must be a dictionary.")
        return value

    def update(self, instance, validated_data): 
        print("Validated Data",validated_data,flush=True)
        user = update_user(instance, validated_data)
        return user