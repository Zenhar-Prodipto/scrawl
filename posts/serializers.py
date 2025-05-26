from rest_framework import serializers
from users.models import User
from .models import Post, PostImage, Tag, Like, Comment
from .services import create_post

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