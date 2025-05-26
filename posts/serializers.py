from rest_framework import serializers
from users.models import User
from .models import Post, PostImage, Tag, Like, Comment
from .services import create_post,update_post

class PostImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ['image_url', 'order']

    def validate_image_url(self, value):
        if not value.startswith('http'):
            raise serializers.ValidationError("Image URL must start with 'http' or 'https'.")
        return value

class PostCreateSerializer(serializers.ModelSerializer):
    post_images = PostImageCreateSerializer(many=True, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True),
        min_length=1,
        max_length=10
    )
    privacy = serializers.ChoiceField(choices=Post.PRIVACY_CHOICES, default='public')
    text = serializers.CharField(max_length=500, allow_blank=True, required=False)

    class Meta:
        model = Post
        fields = ['text', 'tags', 'privacy', 'post_images']

    def validate_text(self, value):
        if value and len(value) > 500:
            raise serializers.ValidationError("Text cannot exceed 500 characters.")
        return value

    def validate_tags(self, value):
        if not value or len(value) < 1:
            raise serializers.ValidationError("At least one tag is required.")
        for tag in value:
            tag = tag.strip()
            if not tag or len(tag) < 1:
                raise serializers.ValidationError("Each tag must be at least 1 character long and cannot be empty.")
            if len(tag) > 50:
                raise serializers.ValidationError("Each tag cannot exceed 50 characters.")
        return value

    def save(self, **kwargs):
        user = kwargs.pop('user')
        validated_data = dict(self.validated_data)
        tags_data = validated_data.pop('tags')
        return create_post(user, validated_data, tags_data)
    

class UserPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'profile_picture','bio']
    
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['name']

class PostImageGetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ['id','image_url', 'order']

class LikeSerializer(serializers.ModelSerializer):
    user = UserPostSerializer(read_only=True)

    class Meta:
        model = Like
        fields = ['id','user', 'created_at']

class CommentSerializer(serializers.ModelSerializer):
    user = UserPostSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'text', 'created_at']

class PostDetailSerializer(serializers.ModelSerializer):
    post_images = PostImageGetSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    likes = LikeSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    liked_by_user = serializers.SerializerMethodField()
    total_likes = serializers.SerializerMethodField()
    total_comments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'text', 'tags', 'privacy', 'post_images', 'likes', 'liked_by_user', 'comments','total_likes','total_comments', 'created_at', 'updated_at']

    def get_liked_by_user(self, obj):
        user = self.context['request'].user
        return Like.objects.filter(post=obj, user=user).exists()
    
    def get_total_likes(self, obj):
        return obj.likes.count()

    def get_total_comments(self, obj):
        return obj.comments.count()
    
    
class PostListSerializer(serializers.ModelSerializer):
    post_images = PostImageGetSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    liked_by_user = serializers.SerializerMethodField()
    total_likes = serializers.SerializerMethodField()
    total_comments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'text', 'tags', 'privacy', 'post_images', 'liked_by_user', 'total_likes', 'total_comments', 'created_at', 'updated_at']

    def get_liked_by_user(self, obj):
        user = self.context['request'].user
        return Like.objects.filter(post=obj, user=user).exists()

    def get_total_likes(self, obj):
        return obj.likes.count()

    def get_total_comments(self, obj):
        return obj.comments.count()
    
    
class PostUpdateSerializer(serializers.ModelSerializer):
    post_images_to_add = PostImageCreateSerializer(many=True, required=False)
    post_images_to_remove = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False
    )
    tags_to_add = serializers.ListField(
        child=serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True),
        max_length=10,
        required=False
    )
    tags_to_remove = serializers.ListField(
        child=serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True),
        max_length=10,
        required=False
    )
    privacy = serializers.ChoiceField(choices=Post.PRIVACY_CHOICES, required=False)
    text = serializers.CharField(max_length=500, allow_blank=True, required=False)

    class Meta:
        model = Post
        fields = ['text', 'privacy', 'post_images_to_add', 'post_images_to_remove', 'tags_to_add', 'tags_to_remove']

    def validate_text(self, value):
        if value and len(value) > 500:
            raise serializers.ValidationError("Text cannot exceed 500 characters.")
        return value

    def validate_tags_to_add(self, value):
        if value:
            for tag in value:
                tag = tag.strip()
                if not tag or len(tag) < 1:
                    raise serializers.ValidationError("Each tag to add must be at least 1 character long and cannot be empty.")
                if len(tag) > 50:
                    raise serializers.ValidationError("Each tag cannot exceed 50 characters.")
        return value

    def validate_tags_to_remove(self, value):
        if value:
            for tag in value:
                tag = tag.strip()
                if not tag or len(tag) < 1:
                    raise serializers.ValidationError("Each tag to remove must be at least 1 character long and cannot be empty.")
                if len(tag) > 50:
                    raise serializers.ValidationError("Each tag cannot exceed 50 characters.")
        return value

    def validate(self, data):
        # Ensure at least one tag remains after updates
        if 'tags_to_add' in data or 'tags_to_remove' in data:
            instance = self.instance
            current_tags = set(tag.name for tag in instance.tags.all())
            
            tags_to_add = set(data.get('tags_to_add', []))
            tags_to_remove = set(data.get('tags_to_remove', []))
            
            # Calculate the resulting tags
            resulting_tags = (current_tags - tags_to_remove) | tags_to_add
            
            if len(resulting_tags) < 1:
                raise serializers.ValidationError("Post must have at least one tag after update.")
            
            # Check total tags after update
            if len(resulting_tags) > 10:
                raise serializers.ValidationError("Post cannot have more than 10 tags after update.")
        
        # Validate post images to remove
        if 'post_images_to_remove' in data:
            instance = self.instance
            existing_image_ids = set(image.id for image in instance.post_images.all())
            images_to_remove = set(data['post_images_to_remove'])
            
            # Check if all images to remove exist
            invalid_ids = images_to_remove - existing_image_ids
            if invalid_ids:
                raise serializers.ValidationError(f"Invalid image IDs to remove: {invalid_ids}")
        
        return data

    def save(self, **kwargs):
        user = kwargs.pop('user')
        validated_data = dict(self.validated_data)
        return update_post(self.instance, user, validated_data)